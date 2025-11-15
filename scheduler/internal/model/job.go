package model

// Job represents a feed processing job
type Job struct {
	FeedID             int64
	Name               string
	URL                string
	Category           string
	PollingInterval    int
	ETag               string
	LastModified       string
	FetchFullContent   bool
	ParsingErrorCount  int
}

// JobList represents a list of jobs
type JobList []Job

// FeedURLs returns a list of feed URLs from the job list
func (jl *JobList) FeedURLs() []string {
	feedURLs := make([]string, len(*jl))
	for i, job := range *jl {
		feedURLs[i] = job.URL
	}
	return feedURLs
}

// FeedNames returns a list of feed names from the job list
func (jl *JobList) FeedNames() []string {
	feedNames := make([]string, len(*jl))
	for i, job := range *jl {
		feedNames[i] = job.Name
	}
	return feedNames
}
