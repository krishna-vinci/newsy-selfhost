package main

import (
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/krishna/newsy-scheduler/internal/config"
	"github.com/krishna/newsy-scheduler/internal/storage"
	"github.com/krishna/newsy-scheduler/internal/worker"
)

func main() {
	// Setup logging
	setupLogging()

	// Initialize configuration
	config.InitOptions()

	// Connect to database
	store, err := storage.NewStorage()
	if err != nil {
		slog.Error("Failed to connect to database", slog.Any("error", err))
		os.Exit(1)
	}
	defer store.Close()

	// Ensure database schema is ready
	if err := store.EnsureSchema(); err != nil {
		slog.Error("Failed to ensure database schema", slog.Any("error", err))
		os.Exit(1)
	}

	// Create worker pool
	pool := worker.NewPool(store, config.Opts.WorkerPoolSize, config.Opts.PythonBackendURL)
	slog.Info("Worker pool created",
		slog.Int("worker_count", config.Opts.WorkerPoolSize),
		slog.String("python_backend_url", config.Opts.PythonBackendURL),
	)

	// Start scheduler
	runScheduler(store, pool)

	// Start HTTP server for health checks
	go startHealthServer()

	// Wait for shutdown signal
	slog.Info("Scheduler service started successfully")
	waitForShutdown()
}

func setupLogging() {
	var logLevel slog.Level
	switch os.Getenv("LOG_LEVEL") {
	case "debug":
		logLevel = slog.LevelDebug
	case "info":
		logLevel = slog.LevelInfo
	case "warn":
		logLevel = slog.LevelWarn
	case "error":
		logLevel = slog.LevelError
	default:
		logLevel = slog.LevelInfo
	}

	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: logLevel,
	}))
	slog.SetDefault(logger)
}

func startHealthServer() {
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy"}`))
	})

	port := config.Opts.ServerPort
	slog.Info("Health check server starting", slog.String("port", port))
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		slog.Error("Health server failed", slog.Any("error", err))
	}
}

func waitForShutdown() {
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	slog.Info("Shutdown signal received, exiting...")
}
