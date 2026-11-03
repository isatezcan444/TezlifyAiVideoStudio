import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[#7367F0]/15 text-[#7367F0] dark:bg-[#7367F0]/25 dark:text-[#A59DF8]",
        secondary:
          "border-transparent bg-slate-100 text-slate-800 dark:bg-white/[0.08] dark:text-slate-300",
        destructive:
          "border-transparent bg-[#EA5455]/15 text-[#EA5455] dark:bg-[#EA5455]/25 dark:text-[#FF7F80]",
        success:
          "border-transparent bg-[#28C76F]/15 text-[#28C76F] dark:bg-[#28C76F]/25 dark:text-[#5CE698]",
        warning:
          "border-transparent bg-[#FF9F43]/15 text-[#FF9F43] dark:bg-[#FF9F43]/25 dark:text-[#FFC285]",
        info:
          "border-transparent bg-[#00CFE8]/15 text-[#00CFE8] dark:bg-[#00CFE8]/25 dark:text-[#46E1F6]",
        outline:
          "text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/[0.12]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
