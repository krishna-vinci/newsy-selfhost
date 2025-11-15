package storage

import (
	"database/sql"
	"fmt"
	"log/slog"
	"net/url"
	"strconv"
	"strings"

	"github.com/krishna/newsy-scheduler/internal/model"
)

type BatchBuilder struct {
	db           *sql.DB
	args         []interface{}
	conditions   []string
	batchSize    int
	limitPerHost int
}

func (b *BatchBuilder) WithBatchSize(batchSize int) *BatchBuilder {
	b.batchSize = batchSize
	return b
}

func (b *BatchBuilder) WithErrorLimit(limit int) *BatchBuilder {
	if limit > 0 {
		b.conditions = append(b.conditions, "COALESCE(parsing_error_count, 0) < $"+strconv.Itoa(len(b.args)+1))
		b.args = append(b.args, limit)
	}
	return b
}

func (b *BatchBuilder) WithNextCheckExpired() *BatchBuilder {
	b.conditions = append(b.conditions, "next_check_at < NOW()")
	return b
}

func (b *BatchBuilder) WithActiveFeeds() *BatchBuilder {
	b.conditions = append(b.conditions, `"isActive" = true`)
	return b
}

func (b *BatchBuilder) WithLimitPerHost(limit int) *BatchBuilder {
	if limit > 0 {
		b.limitPerHost = limit
	}
	return b
}

// FetchJobs retrieves a batch of jobs based on the conditions set in the builder
func (b *BatchBuilder) FetchJobs() (model.JobList, error) {
	query := `
		SELECT 
			id, 
			name, 
			url, 
			category, 
			COALESCE(polling_interval, 60) as polling_interval,
			COALESCE(etag_header, '') as etag_header,
			COALESCE(last_modified_header, '') as last_modified_header,
			COALESCE(fetch_full_content, false) as fetch_full_content,
			COALESCE(parsing_error_count, 0) as parsing_error_count
		FROM feeds
	`

	if len(b.conditions) > 0 {
		query += " WHERE " + strings.Join(b.conditions, " AND ")
	}

	query += " ORDER BY next_check_at ASC"

	if b.batchSize > 0 {
		query += " LIMIT " + strconv.Itoa(b.batchSize)
	}

	rows, err := b.db.Query(query, b.args...)
	if err != nil {
		return nil, fmt.Errorf("unable to fetch batch of jobs: %w", err)
	}
	defer rows.Close()

	jobs := make(model.JobList, 0, b.batchSize)
	hosts := make(map[string]int)
	nbRows := 0
	nbSkippedFeeds := 0

	for rows.Next() {
		var job model.Job
		if err := rows.Scan(
			&job.FeedID,
			&job.Name,
			&job.URL,
			&job.Category,
			&job.PollingInterval,
			&job.ETag,
			&job.LastModified,
			&job.FetchFullContent,
			&job.ParsingErrorCount,
		); err != nil {
			return nil, fmt.Errorf("unable to scan job record: %w", err)
		}

		nbRows++

		// Apply per-host limiting
		if b.limitPerHost > 0 {
			feedHostname := extractDomain(job.URL)
			if hosts[feedHostname] >= b.limitPerHost {
				slog.Debug("Feed host limit reached for this batch",
					slog.String("feed_url", job.URL),
					slog.String("feed_hostname", feedHostname),
					slog.Int("limit_per_host", b.limitPerHost),
					slog.Int("current", hosts[feedHostname]),
				)
				nbSkippedFeeds++
				continue
			}
			hosts[feedHostname]++
		}

		jobs = append(jobs, job)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating on job records: %w", err)
	}

	slog.Info("Created a batch of feeds",
		slog.Int("batch_size", b.batchSize),
		slog.Int("rows_count", nbRows),
		slog.Int("skipped_feeds_count", nbSkippedFeeds),
		slog.Int("jobs_count", len(jobs)),
	)

	return jobs, nil
}

// extractDomain extracts the domain from a URL
func extractDomain(rawURL string) string {
	parsedURL, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	return parsedURL.Host
}
