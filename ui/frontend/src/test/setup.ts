import '@testing-library/jest-dom';
import React from 'react';

// Polyfill ResizeObserver for jsdom (needed by ReactFlow)
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual('framer-motion');

  // Cache component factories so React sees stable references across re-renders
  const componentCache = new Map<string, React.FC<any>>();

  function getMotionComponent(tag: string): React.FC<any> {
    if (!componentCache.has(tag)) {
      const Component = React.forwardRef<any, any>(
        ({ children, className, onClick, style, title, ...rest }, ref) => {
          return React.createElement(
            tag,
            {
              ref,
              className,
              onClick,
              style,
              title,
              'data-testid': rest['data-testid'],
              disabled: rest.disabled,
              role: rest.role,
              type: rest.type,
              'aria-label': rest['aria-label'],
            },
            children
          );
        }
      );
      Component.displayName = `motion.${tag}`;
      componentCache.set(tag, Component as unknown as React.FC<any>);
    }
    return componentCache.get(tag)!;
  }

  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => children,
    motion: new Proxy(
      {},
      {
        get: (_target, prop: string) => getMotionComponent(prop),
      }
    ),
  };
});

// Mock socket.io-client
vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
    close: vi.fn(),
    connected: false,
  })),
}));
