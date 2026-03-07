'use client'

import { useState, useEffect } from 'react'
import {
  Play,
  Trash2,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  Plus,
} from 'lucide-react'

interface CronJob {
  id: string
  name: string
  schedule: string
  status: 'active' | 'paused' | 'error'
  lastRun: string
  nextRun: string
  payload: any
}

export default function CronPanel() {
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

  const getStatusIcon = (status: CronJob['status']) => {
    switch (status) {
      case 'active':
        return <CheckCircle size={20} className="text-green-400" />
      case 'paused':
        return <Clock size={20} className="text-yellow-400" />
      case 'error':
        return <XCircle size={20} className="text-red-400" />
    }
  }

  const handleRunJob = async (jobId: string) => {
    // API call to run job manually
    console.log(`Running job ${jobId}`)
  }

  const handleDeleteJob = (jobId: string) => {
    if (confirm('Are you sure you want to delete this cron job?')) {
      setJobs(prev => prev.filter(job => job.id !== jobId))
    }
  }

  const parseCronSchedule = (schedule: string) => {
    // Simple cron parser for display
    const parts = schedule.split(' ')
    return `${parts[0]} ${parts[1]} ${parts[2]} ${parts[3]} ${parts[4]}`
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Calendar className="text-primary-500" />
            Cron Jobs
          </h1>
          <p className="text-gray-400 mt-1">
            Manage scheduled tasks and automation
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus size={20} />
          Create Job
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="text-sm text-gray-400 mb-1">Total Jobs</div>
          <div className="text-3xl font-bold text-white">{jobs.length}</div>
        </div>
        <div className="card">
          <div className="text-sm text-gray-400 mb-1">Active Jobs</div>
          <div className="text-3xl font-bold text-green-400">
            {jobs.filter(j => j.status === 'active').length}
          </div>
        </div>
        <div className="card">
          <div className="text-sm text-gray-400 mb-1">Jobs with Errors</div>
          <div className="text-3xl font-bold text-red-400">
            {jobs.filter(j => j.status === 'error').length}
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="card">
        <h2 className="text-xl font-bold text-white mb-4">All Cron Jobs</h2>
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
                    <div className="flex items-center gap-2">
                      {getStatusIcon(job.status)}
                      <span className={`capitalize ${
                        job.status === 'active' ? 'text-green-400' :
                        job.status === 'paused' ? 'text-yellow-400' :
                        'text-red-400'
                      }`}>
                        {job.status}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 text-gray-400">{job.lastRun}</td>
                  <td className="py-4 text-gray-400">{job.nextRun}</td>
                  <td className="py-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleRunJob(job.id)}
                        className="btn btn-primary text-sm flex items-center gap-1 px-3"
                      >
                        <Play size={16} />
                        Run Now
                      </button>
                      <button
                        onClick={() => handleDeleteJob(job.id)}
                        className="btn btn-danger text-sm flex items-center gap-1 px-3"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal Placeholder */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="card max-w-2xl w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">Create Cron Job</h3>
            <p className="text-gray-400 mb-4">
              Create job modal - Form implementation required
            </p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowCreateModal(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
