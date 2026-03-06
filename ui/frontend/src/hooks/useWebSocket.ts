import type { WebSocketEvents } from '@/types';
import { useCallback, useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:5000';

export function useWebSocket(projectId?: number) {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // Initialize socket
    const socket = io(WS_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
    });

    socketRef.current = socket;

    // Connection handlers
    socket.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);

      // Subscribe to project if provided
      if (projectId) {
        socket.emit('subscribe', { project_id: projectId });
      }
    });

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    });

    socket.on('connected', (data: any) => {
      console.log('Server acknowledged connection:', data);
    });

    // Cleanup
    return () => {
      if (projectId) {
        socket.emit('unsubscribe', { project_id: projectId });
      }
      socket.close();
    };
  }, [projectId]);

  const subscribe = useCallback(
    <K extends keyof WebSocketEvents>(
      eventName: K,
      callback: (data: WebSocketEvents[K]) => void
    ) => {
      if (!socketRef.current) return () => {};

      socketRef.current.on(eventName as string, callback as any);

      // Return unsubscribe function
      return () => {
        socketRef.current?.off(eventName as string, callback as any);
      };
    },
    []
  );

  const emit = useCallback((eventName: string, data: any) => {
    if (!socketRef.current) return;
    socketRef.current.emit(eventName, data);
  }, []);

  return {
    connected,
    subscribe,
    emit,
    socket: socketRef.current,
  };
}
