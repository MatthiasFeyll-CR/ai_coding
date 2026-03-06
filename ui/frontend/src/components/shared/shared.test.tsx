/**
 * Tests for shared UI components: Badge, Card, Button, EmptyState.
 */
import { Badge } from '@/components/shared/Badge';
import { Button } from '@/components/shared/Button';
import { Card } from '@/components/shared/Card';
import { EmptyState } from '@/components/shared/EmptyState';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

describe('Badge', () => {
  it('renders text', () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('applies variant class', () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    expect(container.firstChild).toHaveClass('bg-status-success/20');
  });
});

describe('Card', () => {
  it('renders title and children', () => {
    render(<Card title="My Card">Content here</Card>);
    expect(screen.getByText('My Card')).toBeInTheDocument();
    expect(screen.getByText('Content here')).toBeInTheDocument();
  });

  it('renders without title', () => {
    render(<Card>Just content</Card>);
    expect(screen.getByText('Just content')).toBeInTheDocument();
  });
});

describe('Button', () => {
  it('renders label', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('calls onClick', async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<Button onClick={handler}>Click</Button>);

    await user.click(screen.getByRole('button'));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('is disabled when loading', () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Button disabled>Nope</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="Nothing" description="No data" />);
    expect(screen.getByText('Nothing')).toBeInTheDocument();
    expect(screen.getByText('No data')).toBeInTheDocument();
  });

  it('renders action button when provided', async () => {
    const user = userEvent.setup();
    const action = vi.fn();
    render(
      <EmptyState
        title="Empty"
        description="Try adding something"
        actionLabel="Add"
        onAction={action}
      />
    );

    const btn = screen.getByRole('button', { name: 'Add' });
    expect(btn).toBeInTheDocument();
    await user.click(btn);
    expect(action).toHaveBeenCalledOnce();
  });
});
