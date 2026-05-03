/**
 * Sentinel V2 protected file. Do NOT modify from inside an agent.
 *
 * `cn` (className) helper that merges Tailwind classes safely. Every
 * component in `components/ui/*` imports `cn` from this file. The build
 * agent has historically forgotten to write this helper, leaving every
 * UI primitive with an unresolved `Module not found: Can't resolve
 * '@/lib/utils'` error and crashing `npm run build` for the whole
 * workspace. Canonicalise it.
 */
export type ClassValue =
  | string
  | number
  | bigint
  | boolean
  | null
  | undefined
  | ClassValue[]
  | { [k: string]: unknown };

function flatten(value: ClassValue): string {
  if (value === null || value === undefined || value === false || value === true) {
    return "";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "bigint") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(flatten).filter(Boolean).join(" ");
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, v]) => Boolean(v))
      .map(([k]) => k)
      .join(" ");
  }
  return "";
}

export function cn(...inputs: ClassValue[]): string {
  return inputs.map(flatten).filter(Boolean).join(" ");
}
