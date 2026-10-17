# ratelimit

A token-bucket rate limiter for Go services. Import `example.invalid/ratelimit`.

## Requirements

Go 1.22 or later. The module has no third-party dependencies.

## Usage

```go
limiter := ratelimit.New(10, 100*time.Millisecond)
if !limiter.Allow() {
	// reject the request
}
```

`New` returns a full bucket that gains one token per interval, up to its capacity.

## Validation

```bash
go test ./...
```

CI runs the same command on every push and pull request.
