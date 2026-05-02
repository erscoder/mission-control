/**
 * Sentinel V2 protected file. Do NOT modify.
 *
 * Global Prisma module. Marked @Global so PrismaService is injectable
 * anywhere in the app without re-importing PrismaModule per feature
 * module. Build agents MUST register this module in AppModule's imports
 * array for runtime DI to resolve PrismaService injections.
 */
import { Global, Module } from '@nestjs/common';

import { PrismaService } from './prisma.service';

@Global()
@Module({
  providers: [PrismaService],
  exports: [PrismaService],
})
export class PrismaModule {}
