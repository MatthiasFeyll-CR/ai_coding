import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon | string;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon: Icon, title, description, action, actionLabel, onAction }: EmptyStateProps) {
  const effectiveAction = action || (actionLabel && onAction ? { label: actionLabel, onClick: onAction } : undefined);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center h-full min-h-[400px] text-center"
    >
      {Icon && (
        typeof Icon === 'string'
          ? <span className="text-6xl mb-4">{Icon}</span>
          : <Icon className="w-16 h-16 mb-4 text-text-muted" />
      )}
      <h2 className="text-xl font-semibold mb-2">{title}</h2>
      <p className="text-text-secondary mb-6 max-w-md">{description}</p>
      {effectiveAction && (
        <button
          onClick={effectiveAction.onClick}
          className="px-6 py-3 bg-accent-cyan text-white rounded-lg hover:bg-accent-cyan/90 transition-colors font-medium"
        >
          {effectiveAction.label}
        </button>
      )}
    </motion.div>
  );
}
