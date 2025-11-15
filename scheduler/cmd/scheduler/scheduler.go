package main

import (
	"log/slog"
	"time"

	"github.com/krishna/newsy-scheduler/internal/config"
	"github.com/krishna/newsy-scheduler/internal/storage"
	"github.com/krishna/newsy-scheduler/internal/worker"
)

func runScheduler(store *storage.Storage, pool *worker.Pool) {
	slog.Debug("Starting background scheduler...")

	go feedScheduler(
		store,
		pool,
		config.Opts.PollingFrequency,
		config.Opts.BatchSize,
		config.Opts.PollingErrorLimit,
		config.Opts.PollingLimitPerHost,
	)

	go cleanupScheduler(
		store,
		config.Opts.CleanupFrequency,
	)
}

func feedScheduler(store *storage.Storage, pool *worker.Pool, frequency time.Duration, batchSize, errorLimit, limitPerHost int) {
	slog.Info("Feed scheduler started",
		slog.Duration("frequency", frequency),
		slog.Int("batch_size", batchSize),
	)

	for range time.Tick(frequency) {
		// Generate a batch of feeds for any user that has feeds to refresh
		batchBuilder := store.NewBatchBuilder()
		batchBuilder.WithBatchSize(batchSize)
		batchBuilder.WithErrorLimit(errorLimit)
		batchBuilder.WithActiveFeeds()
		batchBuilder.WithNextCheckExpired()
		batchBuilder.WithLimitPerHost(limitPerHost)

		if jobs, err := batchBuilder.FetchJobs(); err != nil {
			slog.Error("Unable to fetch jobs from database", slog.Any("error", err))
		} else if len(jobs) > 0 {
			slog.Debug("Feed URLs in this batch", slog.Any("feed_urls", jobs.FeedURLs()))
			pool.Push(jobs)
		}
	}
}

func cleanupScheduler(store *storage.Storage, frequency time.Duration) {
	slog.Info("Cleanup scheduler started",
		slog.Duration("frequency", frequency),
	)

	for range time.Tick(frequency) {
		slog.Info("Running cleanup tasks...")
		// Cleanup is handled by Python backend for now
		// We could implement it here later if needed
	}
}
