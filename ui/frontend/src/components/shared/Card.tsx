import clsx from 'clsx';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  action?: React.ReactNode;
}

export function Card({ children, className, title, action }: CardProps) {
  return (
    <div className={clsx('bg-bg-secondary rounded-lg border border-border-subtle', className)}>
      {title && (
        <div className="flex items-center justify-between p-4 border-b border-border-subtle">
          <h3 className="text-lg font-semibold">{title}</h3>
          {action}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}
