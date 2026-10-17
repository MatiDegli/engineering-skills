package ratelimit

import (
	"testing"
	"time"
)

func TestAllowUntilEmpty(t *testing.T) {
	l := New(2, time.Hour)
	if !l.Allow() || !l.Allow() {
		t.Fatal("a full limiter should allow its capacity")
	}
	if l.Allow() {
		t.Fatal("an empty limiter should refuse")
	}
}

func TestRefill(t *testing.T) {
	l := New(1, 20*time.Millisecond)
	l.Allow()
	time.Sleep(30 * time.Millisecond)
	if !l.Allow() {
		t.Fatal("the limiter should have refilled one token")
	}
}
