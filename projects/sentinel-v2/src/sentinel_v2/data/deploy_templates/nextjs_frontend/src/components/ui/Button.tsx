/**
 * Sentinel V2 protected file. Do NOT modify from inside an agent.
 *
 * Canonical Button primitive. Agents have repeatedly imported `Button`
 * from `@/components/ui/Button` (or relative paths) but forgotten to
 * write the file, breaking every page that uses it and exhausting build
 * retries on `Module not found: Can't resolve '@/components/ui/Button'`.
 * Canonicalise it so every workspace boots with a working primitive.
 *
 * Tailwind-only, no external deps. Variants: primary | secondary | ghost
 * | destructive. Sizes: sm | md | lg.
 */
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 focus:ring-2 focus:ring-blue-500",
  secondary:
    "bg-zinc-200 text-zinc-900 hover:bg-zinc-300 disabled:opacity-50 focus:ring-2 focus:ring-zinc-400 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ghost:
    "bg-transparent text-zinc-900 hover:bg-zinc-100 disabled:opacity-50 focus:ring-2 focus:ring-zinc-400 dark:text-zinc-100 dark:hover:bg-zinc-800",
  destructive:
    "bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 focus:ring-2 focus:ring-red-500",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-md font-medium transition-colors focus:outline-none disabled:cursor-not-allowed",
          VARIANT_CLASSES[variant],
          SIZE_CLASSES[size],
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export default Button;
