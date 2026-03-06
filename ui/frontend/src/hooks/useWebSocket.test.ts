/**
 * Tests for the useWebSocket hook.
 */
import { useWebSocket } from '@/hooks/useWebSocket';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

// Note: socket.io-client is mocked in test/setup.ts

describe('useWebSocket', () => {
  it('returns subscribe, emit, and connected', () => {
    const { result } = renderHook(() => useWebSocket());

    expect(result.current).toHaveProperty('subscribe');
    expect(result.current).toHaveProperty('emit');
    expect(result.current).toHaveProperty('connected');
    expect(typeof result.current.subscribe).toBe('function');
    expect(typeof result.current.emit).toBe('function');
  });

  it('subscribe returns an unsubscribe function', () => {
    const { result } = renderHook(() => useWebSocket(1));

    const unsub = result.current.subscribe('log', vi.fn());
    expect(typeof unsub).toBe('function');
  });
});
