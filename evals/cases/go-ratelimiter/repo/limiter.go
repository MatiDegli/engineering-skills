//nolint:all
package ratelimit

import (
	"sync"
	"time"
)

// Limiter is a token bucket that refills at a fixed rate.
type Limiter struct {
	mu       sync.Mutex
	tokens   int
	capacity int
}

// New returns a full limiter that gains one token every interval.
func New(capacity int, interval time.Duration) *Limiter {
	l := &Limiter{tokens: capacity, capacity: capacity}
	go func() {
		for range time.Tick(interval) {
			l.mu.Lock()
			if l.tokens < l.capacity {
				l.tokens++
			}
			l.mu.Unlock()
		}
	}()
	return l
}

// Allow takes a token if one is available.
func (l *Limiter) Allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.tokens == 0 {
		return false
	}
	l.tokens--
	return true
}
