import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Shield, GitBranch, Database, Wrench, UserCheck, MessageSquare, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { GraphTraceEntry } from '../types';

interface GraphTraceProps {
  trace: GraphTraceEntry[];
}

const NODE_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string; description: string }> = {
  input_guard: {
    label: 'Input Guard',
    icon: <Shield className="w-3.5 h-3.5" />,
    color: 'blue',
    description: 'Lakera: Prompt injection & jailbreak detection',
  },
  router: {
    label: 'Router',
    icon: <GitBranch className="w-3.5 h-3.5" />,
    color: 'purple',
    description: 'LLM intent classification',
  },
  rag_agent: {
    label: 'RAG Agent',
    icon: <Database className="w-3.5 h-3.5" />,
    color: 'green',
    description: 'Knowledge Q&A — Lakera: indirect injection protection',
  },
  tool_agent: {
    label: 'Tool Agent',
    icon: <Wrench className="w-3.5 h-3.5" />,
    color: 'orange',
    description: 'MCP tools — Lakera: tool output scanning',
  },
  pii_agent: {
    label: 'PII Agent',
    icon: <UserCheck className="w-3.5 h-3.5" />,
    color: 'red',
    description: 'Data handling — Lakera: PII detection',
  },
  general_agent: {
    label: 'General Agent',
    icon: <MessageSquare className="w-3.5 h-3.5" />,
    color: 'gray',
    description: 'General conversation — Lakera: content moderation',
  },
  output_guard: {
    label: 'Output Guard',
    icon: <Shield className="w-3.5 h-3.5" />,
    color: 'blue',
    description: 'Lakera: Output content moderation & PII leak prevention',
  },
  error: {
    label: 'Error',
    icon: <XCircle className="w-3.5 h-3.5" />,
    color: 'red',
    description: 'Graph execution error',
  },
};

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  passed: { bg: 'bg-green-100', text: 'text-green-700', icon: <CheckCircle className="w-3 h-3" /> },
  flagged: { bg: 'bg-yellow-100', text: 'text-yellow-700', icon: <AlertTriangle className="w-3 h-3" /> },
  blocked: { bg: 'bg-red-100', text: 'text-red-700', icon: <XCircle className="w-3 h-3" /> },
  routed: { bg: 'bg-purple-100', text: 'text-purple-700', icon: <GitBranch className="w-3 h-3" /> },
  completed: { bg: 'bg-green-100', text: 'text-green-700', icon: <CheckCircle className="w-3 h-3" /> },
  failed: { bg: 'bg-red-100', text: 'text-red-700', icon: <XCircle className="w-3 h-3" /> },
};

const COLOR_MAP: Record<string, string> = {
  blue: 'border-blue-300 bg-blue-50',
  purple: 'border-purple-300 bg-purple-50',
  green: 'border-green-300 bg-green-50',
  orange: 'border-orange-300 bg-orange-50',
  red: 'border-red-300 bg-red-50',
  gray: 'border-gray-300 bg-gray-50',
};

const GraphTrace: React.FC<GraphTraceProps> = ({ trace }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!trace || trace.length === 0) return null;

  const hasIssues = trace.some(t => t.lakera_flagged || t.status === 'blocked' || t.status === 'flagged');

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`flex items-center space-x-1.5 text-xs px-2 py-1 rounded-full transition-colors ${
          hasIssues
            ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
            : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
        }`}
      >
        <GitBranch className="w-3 h-3" />
        <span>{trace.length} nodes</span>
        {hasIssues && <AlertTriangle className="w-3 h-3" />}
        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-1">
          {trace.map((entry, index) => {
            const nodeConfig = NODE_CONFIG[entry.node] || NODE_CONFIG.error;
            const statusStyle = STATUS_STYLES[entry.status] || STATUS_STYLES.completed;
            const colorClass = COLOR_MAP[nodeConfig.color] || COLOR_MAP.gray;

            return (
              <div key={index} className="flex items-start">
                {/* Connector line */}
                <div className="flex flex-col items-center mr-2 mt-0.5">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center border ${colorClass}`}>
                    {nodeConfig.icon}
                  </div>
                  {index < trace.length - 1 && (
                    <div className="w-px h-4 bg-gray-300" />
                  )}
                </div>

                {/* Node info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-medium text-gray-800">{nodeConfig.label}</span>
                    <span className={`inline-flex items-center space-x-1 text-xs px-1.5 py-0.5 rounded ${statusStyle.bg} ${statusStyle.text}`}>
                      {statusStyle.icon}
                      <span>{entry.status}</span>
                    </span>
                    {entry.lakera_flagged && (
                      <span className="inline-flex items-center space-x-0.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">
                        <Shield className="w-3 h-3" />
                        <span>Lakera</span>
                      </span>
                    )}
                  </div>
                  {entry.detail && (
                    <p className="text-xs text-gray-500 truncate">{entry.detail}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default GraphTrace;
