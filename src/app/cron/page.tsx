'use client'

import { useState } from 'react'
import { Calendar, Plus, Play, CheckCircle, Clock, XCircle, Trash2 } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { StatusBadge } from '@/components/ui'
import { PageHeader } from '@/components/layout'

interface CronJob {
  id: string
  name: string
  schedule: string
  status: 'active' | 'paused' | 'error'
  lastRun: string
  nextRun: string
  payload: any
}

export default function CronPage() {
  const [jobs, setJobs] = useState<CronJob[]>([
    {
      id: '1',
      name: 'Daily Standup',
      schedule: '0 9 * * *',
      status: 'active',
      lastRun: '2026-03-07 09:00',
      nextRun: '2026-03-08 09:00',
      payload: { type: 'systemEvent', text: 'Morning standup' },
    },
    {
      id: '2',
      name: 'P&L Report',
      schedule: '0 18 * * *',
      status: 'active',
      lastRun: '2026-03-07 18:00',
      nextRun: '2026-03-08 18:00',
      payload: { type: 'agentTurn', message: 'Generate P&L report' },
    },
    {
      id: '3',
      name: 'Bot Watchdog',
      schedule: '0 */30 * * *',
      status: 'error',
      lastRun: '2026-03-07 16:00',
      nextRun: '2026-03-07 16:30',
      payload: { type: 'systemEvent', text: 'Check bot status' },
    },
  ])

  const [showCreateModal, setShowCreateModal] = useState(false)

  const handleRunJob = async (jobId: string) => {
    console.log(`Running job ${jobId}`)
  }

  const handleDeleteJob = (jobId: string) => {
    if (confirm('Are you sure you want to delete this cron job?')) {
      setJobs(prev => prev.filter(job => job.id !== jobId))
    }
  }

  const parseCronSchedule = (schedule: string) => {
    const parts = schedule.split(' ')
    return `${parts[0]} ${parts[1]} ${parts[2]} ${parts[3]} ${parts[4]}`
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cron Jobs"
        description="Manage scheduled tasks and automation"
        icon={Calendar}
        actions={
          <Button variant="primary" icon={Plus} onClick={() => setShowCreateModal(true)}>
            Create Job
          </Button>
        }
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <div className="text-sm text-gray-400 mb-1">Total Jobs</div>
          <div className="text-3xl font-bold text-white">{jobs.length}</div>
        </Card>
        <Card>
          <div className="text-sm text-gray-400 mb-1">Active Jobs</div>
          <div className="text-3xl font-bold text-green-400">
            {jobs.filter(j => j.status === 'active').length}
          </div>
        </Card>
        <Card>
          <div className="text-sm text-gray-400 mb-1">Jobs with Errors</div>
          <div className="text-3xl font-bold text-red-400">
            {jobs.filter(j => j.status === 'error').length}
          </div>
        </Card>
      </div>

      {/* Jobs Table */}
      <Card title="All Cron Jobs">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-gray-400 text-sm border-b border-dark-600">
                <th className="pb-3">Name</th>
                <th className="pb-3">Schedule</th>
                <th className="pb-3">Status</th>
                <th className="pb-3">Last Run</th>
                <th className="pb-3">Next Run</th>
                <th className="pb-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b border-dark-700">
                  <td className="py-4 text-white font-medium">{job.name}</td>
                  <td className="py-4">
                    <code className="bg-dark-700 px-2 py-1 rounded text-sm text-primary-400">
                      {parseCronSchedule(job.schedule)}
                    </code>
                  </td>
                  <td className="py-4">
                    <StatusBadge status={job.status} icon />
                  </td>
                  <td className="py-4 text-gray-400">{job.lastRun}</td>
                  <td className="py-4 text-gray-400">{job.nextRun}</td>
                  <td className="py-4">
                    <div className="flex gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        icon={Play}
                        onClick={() => handleRunJob(job.id)}
                      >
                        Run Now
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={Trash2}
                        onClick={() => handleDeleteJob(job.id)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <Card>
            <h3 className="text-xl font-bold text-white mb-4">Create Cron Job</h3>
            <p className="text-gray-400 mb-4">
              Create job modal - Form implementation required
            </p>
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => setShowCreateModal(false)}>
                Close
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
