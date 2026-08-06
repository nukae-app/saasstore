import { cva } from 'class-variance-authority';
import { cn } from '../lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-zinc-100 text-zinc-700',
        primary: 'bg-amber-100 text-amber-800',
        secondary: 'bg-secondary text-secondary-foreground',
        outline: 'border border-input text-foreground',
        destructive: 'bg-red-100 text-red-800',
        success: 'bg-green-100 text-green-800',
        warning: 'bg-yellow-100 text-yellow-800',
      },
      color: {
        default: 'bg-zinc-100 text-zinc-700',
        amber:   'bg-amber-100 text-amber-800',
        green:   'bg-green-100 text-green-800',
        blue:    'bg-blue-100 text-blue-800',
        red:     'bg-red-100 text-red-800',
        purple:  'bg-purple-100 text-purple-800',
        yellow:  'bg-yellow-100 text-yellow-800',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export function Badge({ className, variant, color, ...props }) {
  return (
    <span
      className={cn(badgeVariants({ variant: color ? undefined : variant, color }), className)}
      {...props}
    />
  );
}

export { badgeVariants };
