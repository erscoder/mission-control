'use client'

import { useState } from 'react'
import { Folder, FileText, ChevronRight, ChevronDown, Edit3, Save, X, Plus } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { PageHeader } from '@/components/layout'

interface FileNode {
  name: string
  type: 'folder' | 'file'
  path: string
  children?: FileNode[]
  content?: string
}

export default function DocsPage() {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['company', 'projects']))
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [editingContent, setEditingContent] = useState('')
  const [isEditing, setIsEditing] = useState(false)

  const fileTree: FileNode[] = [
    {
      name: 'company',
      type: 'folder',
      path: 'company',
      children: [
        {
          name: 'operating-model.md',
          type: 'file',
          path: 'docs-site/docs/operating-model.md',
          content: '# Operating Model\n\nMission: Build autonomous AI agents that work 24/7\n\n## Core Values\n- Utility first\n- Reliability\n- Scalability',
        },
        {
          name: '30-day-plan.md',
          type: 'file',
          path: 'docs-site/docs/30-day-plan.md',
          content: '# 30-Day Plan\n\nWeek 1: Rescue mode\n- Fix Matías bot\n- Monitor Marcus live\n- Start Diego dry-run',
        },
      ],
    },
    {
      name: 'projects',
      type: 'folder',
      path: 'projects',
      children: [
        {
          name: 'hyperliquid-bot-ml',
          type: 'folder',
          path: 'projects/hyperliquid-bot-ml',
          children: [
            {
              name: 'PROGRESS.md',
              type: 'file',
              path: 'projects/hyperliquid-bot-ml/PROGRESS.md',
              content: '# PROGRESS.md\n\nCurrent Status: LIVE TRADING\n\nLast updated: 2026-03-07',
            },
            {
              name: 'README.md',
              type: 'file',
              path: 'projects/hyperliquid-bot-ml/README.md',
              content: '# Hyperliquid ML Bot\n\nCrypto trading bot with ensemble ML + SMC indicators',
            },
          ],
        },
        {
          name: 'btc-15min-js',
          type: 'folder',
          path: 'projects/btc-15min-js',
          children: [
            {
              name: 'PROGRESS.md',
              type: 'file',
              path: 'projects/btc-15min-js/PROGRESS.md',
              content: '# PROGRESS.md\n\nCurrent Status: BLOCKED - v1.5.9 broken\n\nLast updated: 2026-03-07',
            },
          ],
        },
        {
          name: 'football-bot-nestjs',
          type: 'folder',
          path: 'projects/football-bot-nestjs',
          children: [
            {
              name: 'PROGRESS.md',
              type: 'file',
              path: 'projects/football-bot-nestjs/PROGRESS.md',
              content: '# PROGRESS.md\n\nCurrent Status: DRY RUN\n\nLast updated: 2026-03-06',
            },
          ],
        },
      ],
    },
    {
      name: 'agents',
      type: 'folder',
      path: 'agents',
      children: [
        {
          name: 'harvis',
          type: 'folder',
          path: 'agents/harvis',
          children: [
            {
              name: 'SOUL.md',
              type: 'file',
              path: '~/clawd/SOUL.md',
              content: '# SOUL.md\n\nSoy Harvis. No soy un chatbot — soy el asistente personal de Kike.\n\n## Core Truths\n**Sé genuinamente útil.**',
            },
            {
              name: 'MEMORY.md',
              type: 'file',
              path: '~/clawd/MEMORY.md',
              content: '# MEMORY.md\n\nLong-term memory for Harvis',
            },
          ],
        },
      ],
    },
  ]

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const newSet = new Set(prev)
      if (newSet.has(path)) {
        newSet.delete(path)
      } else {
        newSet.add(path)
      }
      return newSet
    })
  }

  const findFileContent = (nodes: FileNode[], path: string): FileNode | null => {
    for (const node of nodes) {
      if (node.path === path && node.type === 'file') {
        return node
      }
      if (node.children) {
        const found = findFileContent(node.children, path)
        if (found) return found
      }
    }
    return null
  }

  const handleFileClick = (path: string) => {
    const fileNode = findFileContent(fileTree, path)
    if (fileNode && fileNode.content) {
      setSelectedFile(path)
      setEditingContent(fileNode.content)
      setIsEditing(false)
    }
  }

  const handleSave = () => {
    console.log(`Saving file: ${selectedFile}`)
    setIsEditing(false)
  }

  const handleCancel = () => {
    const fileNode = selectedFile ? findFileContent(fileTree, selectedFile) : null
    if (fileNode && fileNode.content) {
      setEditingContent(fileNode.content)
    }
    setIsEditing(false)
  }

  const renderTree = (nodes: FileNode[], level: number = 0) => {
    return nodes.map((node) => {
      const isExpanded = expandedFolders.has(node.path)
      const paddingLeft = level * 20

      if (node.type === 'folder') {
        return (
          <div key={node.path}>
            <div
              className="flex items-center gap-2 py-2 hover:bg-dark-700 rounded cursor-pointer select-none"
              style={{ paddingLeft: `${paddingLeft + 12}px` }}
              onClick={() => toggleFolder(node.path)}
            >
              {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
              <Folder size={18} className="text-yellow-500" />
              <span className="text-white font-medium">{node.name}</span>
            </div>
            {isExpanded && node.children && renderTree(node.children, level + 1)}
          </div>
        )
      } else {
        return (
          <div
            key={node.path}
            className={`flex items-center gap-2 py-2 hover:bg-dark-700 rounded cursor-pointer ${
              selectedFile === node.path ? 'bg-dark-700' : ''
            }`}
            style={{ paddingLeft: `${paddingLeft + 30}px` }}
            onClick={() => handleFileClick(node.path)}
          >
            <FileText size={18} className="text-gray-400" />
            <span className="text-white">{node.name}</span>
          </div>
        )
      }
    })
  }

  return (
    <div className="h-full flex gap-6">
      {/* File Tree */}
      <Card className="w-80 overflow-auto" title="Documentation">
        <div className="space-y-1">
          {renderTree(fileTree)}
        </div>
      </Card>

      {/* File Editor */}
      <div className="flex-1 card flex flex-col">
        {selectedFile ? (
          <>
            <div className="flex items-center justify-between pb-4 border-b border-dark-600 px-6 pt-6">
              <div>
                <h2 className="text-lg font-bold text-white">
                  {selectedFile.split('/').pop()}
                </h2>
                <p className="text-sm text-gray-400">{selectedFile}</p>
              </div>
              <div className="flex gap-2">
                {isEditing ? (
                  <>
                    <Button variant="primary" icon={Save} onClick={handleSave}>
                      Save
                    </Button>
                    <Button variant="secondary" icon={X} onClick={handleCancel}>
                      Cancel
                    </Button>
                  </>
                ) : (
                  <Button variant="secondary" icon={Edit3} onClick={() => setIsEditing(true)}>
                    Edit
                  </Button>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-auto p-6">
              {isEditing ? (
                <textarea
                  value={editingContent}
                  onChange={(e) => setEditingContent(e.target.value)}
                  className="w-full h-full bg-dark-700 text-white font-mono text-sm p-4 rounded border border-dark-600 resize-none focus:outline-none focus:border-primary-500"
                  placeholder="File content..."
                />
              ) : (
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono">
                  {editingContent}
                </pre>
              )}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <FileText size={48} className="mx-auto mb-4" />
              <p>Select a file to view or edit</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
