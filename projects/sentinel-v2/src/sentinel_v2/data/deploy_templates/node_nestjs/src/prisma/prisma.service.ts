/**
 * Sentinel V2 protected file. Do NOT modify.
 *
 * Canonical Prisma data-access service. Lifecycle hooks ensure the
 * Prisma client connects on module init and disconnects on shutdown
 * so Fly.io rolling deploys close DB sockets cleanly. Re-export from
 * the global PrismaModule (./prisma.module) and inject anywhere with
 * the standard NestJS DI pattern:
 *
 *   constructor(private readonly prisma: PrismaService) {}
 *
 * Build agents MUST reference this exact path for imports:
 *   import { PrismaService } from '../../prisma/prisma.service';
 * Rewriting this file is the leading cause of TS2307 import errors at
 * the post-build verification gate.
 */
import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService
  extends PrismaClient
  implements OnModuleInit, OnModuleDestroy
{
  private readonly logger = new Logger(PrismaService.name);

  async onModuleInit(): Promise<void> {
    try {
      await this.$connect();
      this.logger.log('Prisma client connected');
    } catch (err) {
      this.logger.error('Failed to connect Prisma client', err as Error);
      throw err;
    }
  }

  async onModuleDestroy(): Promise<void> {
    await this.$disconnect();
    this.logger.log('Prisma client disconnected');
  }
}
