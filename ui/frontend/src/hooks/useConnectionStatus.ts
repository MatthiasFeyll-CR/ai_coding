import { healthApi } from '@/api/client';
import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:5000';
const HEALTH_POLL_INTERVAL = 10_000; // 10 seconds

interface ConnectionStatus {
  wsConnected: boolean;
  apiConnected: boolean;
  isConnected: boolean;
}

export function useConnectionStatus(): ConnectionStatus {
  const [wsConnected, setWsConnected] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // WebSocket connectivity monitor
  useEffect(() => {
    const socket = io(WS_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionAttempts: Infinity,
    });

    socketRef.current = socket;

    socket.on('connect', () => setWsConnected(true));
    socket.on('disconnect', () => setWsConnected(false));
    socket.on('connect_error', () => setWsConnected(false));

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, []);

  // REST API health polling
  useEffect(() => {
    const checkHealth = async () => {
      try {
        await healthApi.check();
        setApiConnected(true);
      } catch {
        setApiConnected(false);
      }
    };

    // Check immediately on mount
    checkHealth();

    intervalRef.current = setInterval(checkHealth, HEALTH_POLL_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return {
    wsConnected,
    apiConnected,
    isConnected: wsConnected && apiConnected,
  };
}
