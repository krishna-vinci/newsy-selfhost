package worker

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/krishna/newsy-scheduler/internal/model"
	"github.com/krishna/newsy-scheduler/internal/storage"
)

// worker refreshes a feed in the background by calling Python backend
type worker struct {
	id               int
	store            *storage.Storage
	pythonBackendURL string
}

// ProcessFeedRequest is the request payload sent to Python backend
type ProcessFeedRequest struct {
	FeedID           int64  `json:"feed_id"`
	Name             string `json:"name"`
	URL              string `json:"url"`
	Category         string `json:"category"`
	PollingInterval  int    `json:"polling_interval"`
	ETag             string `json:"etag"`
	LastModified     string `json:"last_modified"`
	FetchFullContent bool   `json:"fetch_full_content"`
}

// ProcessFeedResponse is the response from Python backend
type ProcessFeedResponse struct {
	Success      bool   `json:"success"`
	ArticlesAdded int   `json:"articles_added"`
	NewETag      string `json:"new_etag"`
	NewLastModified string `json:"new_last_modified"`
	Error        string `json:"error,omitempty"`
}

// Run waits for a job and processes the given feed
func (w *worker) Run(c <-chan model.Job) {
	slog.Debug("Worker started",
		slog.Int("worker_id", w.id),
	)

	for {
		job := <-c
		slog.Debug("Job received by worker",
			slog.Int("worker_id", w.id),
			slog.Int64("feed_id", job.FeedID),
			slog.String("feed_name", job.Name),
			slog.String("feed_url", job.URL),
		)

		startTime := time.Now()
		err := w.processFeed(job)

		if err != nil {
			slog.Warn("Feed processing failed",
				slog.Int("worker_id", w.id),
				slog.Int64("feed_id", job.FeedID),
				slog.String("feed_name", job.Name),
				slog.Any("error", err),
			)
		} else {
			slog.Info("Feed processed successfully",
				slog.Int("worker_id", w.id),
				slog.Int64("feed_id", job.FeedID),
				slog.String("feed_name", job.Name),
				slog.Duration("duration", time.Since(startTime)),
			)
		}
	}
}

func (w *worker) processFeed(job model.Job) error {
	// Prepare request payload
	reqPayload := ProcessFeedRequest{
		FeedID:           job.FeedID,
		Name:             job.Name,
		URL:              job.URL,
		Category:         job.Category,
		PollingInterval:  job.PollingInterval,
		ETag:             job.ETag,
		LastModified:     job.LastModified,
		FetchFullContent: job.FetchFullContent,
	}

	jsonData, err := json.Marshal(reqPayload)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	// Call Python backend
	url := fmt.Sprintf("%s/internal/process-feed", w.pythonBackendURL)
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{
		Timeout: 10 * time.Minute, // Long timeout for feed processing
	}

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to call Python backend: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Python backend returned error status %d: %s", resp.StatusCode, string(body))
	}

	var respData ProcessFeedResponse
	if err := json.Unmarshal(body, &respData); err != nil {
		return fmt.Errorf("failed to unmarshal response: %w", err)
	}

	if !respData.Success {
		return fmt.Errorf("feed processing failed: %s", respData.Error)
	}

	slog.Debug("Python backend response",
		slog.Int("worker_id", w.id),
		slog.Int64("feed_id", job.FeedID),
		slog.Int("articles_added", respData.ArticlesAdded),
	)

	return nil
}
