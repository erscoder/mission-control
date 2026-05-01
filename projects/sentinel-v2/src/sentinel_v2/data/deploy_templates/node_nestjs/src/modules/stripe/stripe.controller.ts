/**
 * Sentinel V2 protected file. Do NOT modify.
 *
 * Canonical Stripe webhook endpoint. Validates the Stripe-Signature header
 * against the runtime-provisioned signing secret. There is intentionally no
 * fallback: if `stripeConfig.webhookSecret` is empty, the import in
 * `stripe.config.ts` already threw at boot. Any modification that wraps the
 * secret lookup in a `|| ''` or that try/catches the constructEvent call to
 * accept unsigned payloads is an audit regression.
 *
 * Mount path: POST /api/stripe/webhook (matches the URL Sentinel registers
 * with Stripe during the deploy phase).
 */
import {
  Controller,
  Post,
  Req,
  Res,
  HttpStatus,
  RawBodyRequest,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import Stripe from 'stripe';

import { stripeConfig } from '../../config/stripe.config';

const stripeClient = new Stripe(stripeConfig.secretKey, {
  apiVersion: '2024-06-20',
});

@Controller('api/stripe')
export class StripeWebhookController {
  @Post('webhook')
  async handle(
    @Req() req: RawBodyRequest<Request>,
    @Res() res: Response,
  ): Promise<void> {
    const signature = req.headers['stripe-signature'];
    if (!signature || Array.isArray(signature)) {
      res.status(HttpStatus.BAD_REQUEST).json({
        error: 'missing or malformed Stripe-Signature header',
      });
      return;
    }
    const rawBody = req.rawBody;
    if (!rawBody) {
      res.status(HttpStatus.BAD_REQUEST).json({
        error: 'rawBody missing; ensure NestJS bootstrap uses { rawBody: true }',
      });
      return;
    }

    let event: Stripe.Event;
    try {
      event = stripeClient.webhooks.constructEvent(
        rawBody,
        signature,
        stripeConfig.webhookSecret,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.status(HttpStatus.BAD_REQUEST).json({
        error: `webhook signature verification failed: ${message}`,
      });
      return;
    }

    // Per-event handlers belong in dedicated services. The build agent is
    // expected to wire `StripeBillingService.handleEvent(event)` here. We
    // acknowledge with 2xx so Stripe stops retrying; failure to ack within
    // a few seconds causes Stripe to redeliver, which is fine but noisy.
    res.status(HttpStatus.OK).json({ received: true, type: event.type });
  }
}
