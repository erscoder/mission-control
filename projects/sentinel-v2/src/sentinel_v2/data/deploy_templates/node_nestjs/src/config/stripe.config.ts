/**
 * Sentinel V2 protected file. Do NOT modify.
 *
 * Fail-fast Stripe configuration. Throws at module load if either the API
 * key or the webhook signing secret is missing. The Sentinel deploy phase
 * provisions both as Fly secrets via flyctl secrets set; if either ends up
 * empty at runtime we want the app to crash loudly, not silently accept
 * unsigned webhooks (regression of audit blocker F-01).
 *
 * Import this module from your AppModule (or any module loaded at boot)
 * to trigger validation:
 *   import './config/stripe.config';
 */
export interface StripeRuntimeConfig {
  secretKey: string;
  webhookSecret: string;
  productId: string | null;
  priceId: string | null;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === null || value === '') {
    throw new Error(
      `[stripe.config] Required env var ${name} is missing or empty. ` +
        `Refusing to boot with an undefined Stripe credential. ` +
        `Set this via flyctl secrets set ${name}=... on the Fly app.`,
    );
  }
  return value;
}

export const stripeConfig: StripeRuntimeConfig = {
  secretKey: requireEnv('STRIPE_SECRET_KEY'),
  webhookSecret: requireEnv('STRIPE_WEBHOOK_SECRET'),
  productId: process.env.STRIPE_PRODUCT_ID ?? null,
  priceId: process.env.STRIPE_PRICE_ID ?? null,
};
