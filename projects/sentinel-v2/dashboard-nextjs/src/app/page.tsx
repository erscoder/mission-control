'use client'

import { useMemo } from 'react'
import CommandBar from '@/components/CommandBar'
import KPICards from '@/components/KPICards'
import AgentConversation from '@/components/AgentConversation'
import BuildQueue from '@/components/BuildQueue'
import { useSentinelSocket } from '@/hooks/useSentinelSocket'

export default function HomePage() {
  const {
    status,
    flowState,
    breakdown,
    messages,
    drafts,
    buildQueue,
    approveDraft,
    rejectDraft,
    reviseDraft,
    retryDraft,
    approveDeploy,
    rejectDeploy,
  } = useSentinelSocket()

  const activeAgentId = useMemo(() => {
    if (!messages || messages.length === 0) return null
    const last = messages[messages.length - 1]
    return last?.agent_id ?? null
  }, [messages])

  return (
    <div className="relative min-h-screen pb-10">
      <CommandBar status={status} flowState={flowState} breakdown={breakdown} />

      <main className="mx-auto grid w-full max-w-[1800px] grid-cols-12 gap-5 px-6 pt-6">
        {/* Left column — KPIs + unified Build Pipeline (Draft → Deployed) */}
        <div className="col-span-12 flex flex-col gap-5 lg:col-span-8">
          <KPICards drafts={drafts} breakdown={breakdown} />
          <BuildQueue
            queue={buildQueue}
            allDrafts={drafts}
            onApproveDraft={approveDraft}
            onRejectDraft={rejectDraft}
            onReviseDraft={reviseDraft}
            onRetryDraft={retryDraft}
            onApproveDeploy={approveDeploy}
            onRejectDeploy={rejectDeploy}
          />
        </div>

        {/* Right column — Agent Feed */}
        <div className="col-span-12 lg:col-span-4 lg:sticky lg:top-[72px] lg:h-[calc(100vh-92px)]">
          <AgentConversation messages={messages} activeAgentId={activeAgentId} />
        </div>
      </main>
    </div>
  )
}
