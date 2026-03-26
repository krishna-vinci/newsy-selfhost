# Development stage
FROM golang:1.21-alpine AS development
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
# We use go run for development with sync+restart in docker-compose watch
CMD ["go", "run", "./cmd/scheduler"]

# Build stage
FROM golang:1.21-alpine AS builder

WORKDIR /build

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o scheduler ./cmd/scheduler

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/scheduler .

# Set timezone
ENV TZ=Asia/Kolkata

EXPOSE 8667

CMD ["./scheduler"]
