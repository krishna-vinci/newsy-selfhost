package worker

import (
	"github.com/krishna/newsy-scheduler/internal/model"
	"github.com/krishna/newsy-scheduler/internal/storage"
)

// Pool handles a pool of workers
type Pool struct {
	queue chan model.Job
}

// Push sends a list of jobs to the queue
func (p *Pool) Push(jobs model.JobList) {
	for _, job := range jobs {
		p.queue <- job
	}
}

// NewPool creates a pool of background workers
func NewPool(store *storage.Storage, nbWorkers int, pythonBackendURL string) *Pool {
	workerPool := &Pool{
		queue: make(chan model.Job),
	}

	for i := 0; i < nbWorkers; i++ {
		worker := &worker{
			id:               i,
			store:            store,
			pythonBackendURL: pythonBackendURL,
		}
		go worker.Run(workerPool.queue)
	}

	return workerPool
}
