import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Trophy, Users, Clock, ChartBar, Lightning, TrendUp,
  Medal, Crown, ArrowUp, ArrowDown, ChatText,
  WhatsappLogo, Envelope, DeviceMobile, ChatCircleDots,
  CaretRight, ArrowsClockwise, CheckCircle,
} from "@phosphor-icons/react";
import { TelegramLogo } from "@phosphor-icons/react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import useLivePolling from "../../hooks/useLivePolling";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CHANNEL_ICONS = {
  whatsapp: { icon: WhatsappLogo, color: "text-green-500", bg: "bg-green-50" },
  email: { icon: Envelope, color: "text-blue-500", bg: "bg-blue-50" },
  sms: { icon: DeviceMobile, color: "text-purple-500", bg: "bg-purple-50" },
  telegram: { icon: TelegramLogo, color: "text-sky-500", bg: "bg-sky-50" },
  internal: { icon: ChatText, color: "text-stone-500", bg: "bg-stone-50" },
  website_chat: { icon: ChatCircleDots, color: "text-indigo-500", bg: "bg-indigo-50" },
  "booking.com": { icon: ChatText, color: "text-blue-700", bg: "bg-blue-50" },
};

const RANK_STYLES = [
  { bg: "bg-amber-50 border-amber-200", icon: Crown, iconColor: "text-amber-500", badge: "bg-amber-100 text-amber-700" },
  { bg: "bg-stone-50 border-stone-200", icon: Medal, iconColor: "text-stone-400", badge: "bg-stone-100 text-stone-600" },
  { bg: "bg-orange-50 border-orange-200", icon: Medal, iconColor: "text-orange-400", badge: "bg-orange-100 text-orange-600" },
];

function formatResponseTime(min) {
  if (!min || min === 0) return "N/A";
  if (min < 1) return `${Math.round(min * 60)}s`;
  if (min < 60) return `${Math.round(min)}m`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function MetricCard({ icon: Icon, iconColor, iconBg, label, value, sub, testId }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={testId}>
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${iconBg}`}>
          <Icon size={20} className={iconColor} weight="fill" />
        </div>
        <div>
          <div className="text-2xl font-bold text-stone-900 tracking-tight">{value}</div>
          <div className="text-xs text-stone-500">{label}</div>
        </div>
      </div>
      {sub && <div className="text-[11px] text-stone-400 mt-2 pl-[52px]">{sub}</div>}
    </div>
  );
}

function AgentCard({ agent, expanded, onToggle }) {
  const rankIdx = agent.rank - 1;
  const style = rankIdx < 3 ? RANK_STYLES[rankIdx] : { bg: "bg-white border-stone-200", icon: Users, iconColor: "text-stone-400", badge: "bg-stone-100 text-stone-500" };
  const RankIcon = style.icon;
  const channels = Object.entries(agent.channels || {}).sort((a, b) => b[1] - a[1]);
  const maxChannel = channels.length > 0 ? channels[0] : null;

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${style.bg}`} data-testid={`agent-card-${agent.rank}`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 p-4 text-left"
        data-testid={`agent-toggle-${agent.rank}`}
      >
        {/* Rank badge */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${style.badge} font-bold text-sm flex-shrink-0`}>
          {agent.rank <= 3 ? <RankIcon size={16} weight="fill" /> : agent.rank}
        </div>

        {/* Agent name & score */}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-stone-800 truncate">{agent.name}</div>
          <div className="flex items-center gap-2 mt-0.5">
            <div className="text-xs text-stone-500">{agent.total_messages} msgs</div>
            <span className="text-stone-300">|</span>
            <div className="text-xs text-stone-500">{formatResponseTime(agent.avg_response_min)} avg</div>
            <span className="text-stone-300">|</span>
            <div className="text-xs text-stone-500">{agent.resolution_rate}% resolved</div>
          </div>
        </div>

        {/* Score */}
        <div className="flex flex-col items-end flex-shrink-0">
          <div className="text-lg font-bold text-stone-800">{agent.performance_score}</div>
          <div className="text-[10px] text-stone-400 uppercase tracking-wider">score</div>
        </div>

        <CaretRight size={14} className={`text-stone-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-0 space-y-3 border-t border-stone-100">
          {/* Detailed stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3">
            <div className="bg-white/60 rounded-lg p-2.5 text-center">
              <div className="text-base font-bold text-stone-800">{agent.total_messages}</div>
              <div className="text-[10px] text-stone-500">Messages Sent</div>
            </div>
            <div className="bg-white/60 rounded-lg p-2.5 text-center">
              <div className="text-base font-bold text-stone-800">{agent.conversations_count}</div>
              <div className="text-[10px] text-stone-500">Conversations</div>
            </div>
            <div className="bg-white/60 rounded-lg p-2.5 text-center">
              <div className="text-base font-bold text-stone-800">{formatResponseTime(agent.avg_response_min)}</div>
              <div className="text-[10px] text-stone-500">Avg Response</div>
            </div>
            <div className="bg-white/60 rounded-lg p-2.5 text-center">
              <div className="text-base font-bold text-stone-800">{agent.resolution_rate}%</div>
              <div className="text-[10px] text-stone-500">Resolution Rate</div>
            </div>
          </div>

          {/* Response time breakdown */}
          {agent.avg_response_min > 0 && (
            <div className="flex items-center gap-4 text-xs text-stone-500 px-1">
              <span className="flex items-center gap-1"><ArrowDown size={12} className="text-green-500" /> Fastest: {formatResponseTime(agent.fastest_response_min)}</span>
              <span className="flex items-center gap-1"><ArrowUp size={12} className="text-red-400" /> Slowest: {formatResponseTime(agent.slowest_response_min)}</span>
              <span className="flex items-center gap-1"><Lightning size={12} className="text-amber-500" /> {agent.response_count || 0} responses measured</span>
            </div>
          )}

          {/* Conversation status breakdown */}
          {agent.assigned_total > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-medium text-stone-600">Conversation Status ({agent.assigned_total} assigned)</div>
              <div className="flex gap-1.5">
                {agent.resolved > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">{agent.resolved} resolved</span>
                )}
                {agent.in_progress > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">{agent.in_progress} active</span>
                )}
                {agent.waiting > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">{agent.waiting} waiting</span>
                )}
                {agent.new_convs > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-stone-100 text-stone-600 font-medium">{agent.new_convs} new</span>
                )}
              </div>
            </div>
          )}

          {/* Channel breakdown */}
          {channels.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-medium text-stone-600">Channel Breakdown</div>
              <div className="flex flex-wrap gap-2">
                {channels.map(([ch, count]) => {
                  const cfg = CHANNEL_ICONS[ch] || CHANNEL_ICONS.internal;
                  const ChIcon = cfg.icon;
                  return (
                    <div key={ch} className={`flex items-center gap-1.5 px-2 py-1 rounded-lg ${cfg.bg}`}>
                      <ChIcon size={13} className={cfg.color} weight="fill" />
                      <span className="text-[11px] font-medium text-stone-700">{count}</span>
                      <span className="text-[10px] text-stone-400">{ch}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DailyTrendChart({ dailyData, agents }) {
  if (!dailyData || Object.keys(dailyData).length === 0) {
    return (
      <div className="text-center py-8 text-stone-400 text-sm">
        No daily activity data available yet
      </div>
    );
  }

  const days = Object.keys(dailyData).sort();
  const maxCount = Math.max(...days.map(d => Object.values(dailyData[d]).reduce((a, b) => a + b, 0)), 1);

  return (
    <div className="space-y-1" data-testid="daily-trend-chart">
      {days.slice(-14).map(day => {
        const total = Object.values(dailyData[day]).reduce((a, b) => a + b, 0);
        const pct = (total / maxCount) * 100;
        const label = new Date(day + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
        return (
          <div key={day} className="flex items-center gap-2">
            <div className="w-14 text-[11px] text-stone-500 text-right font-mono">{label}</div>
            <div className="flex-1 h-5 bg-stone-100 rounded-md overflow-hidden relative">
              <div
                className="h-full bg-gradient-to-r from-emerald-400 to-teal-500 rounded-md transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
              {total > 0 && (
                <span className="absolute right-2 top-0.5 text-[10px] font-medium text-stone-600">{total}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function StaffPerformancePanel({ properties, activePropertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30");
  const [expandedAgent, setExpandedAgent] = useState(null);

  const propertyId = activePropertyId || "all";

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/staff-performance/${propertyId}?days=${period}`);
      setData(res.data);
    } catch (err) {
      console.error("Failed to fetch staff performance:", err);
    } finally {
      setLoading(false);
    }
  }, [propertyId, period]);

  useEffect(() => { fetchData(); }, [fetchData]);
  // ⚡ Staff performance KPIs refresh every 2min
  useLivePolling(fetchData, { intervalMs: 120000 });
  useEffect(() => { if (data?.agents?.length > 0 && expandedAgent === null) setExpandedAgent(0); }, [data]);

  const team = data?.team_summary || {};
  const agents = data?.agents || [];

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6" data-testid="staff-performance-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="staff-perf-title">
            <Trophy size={22} className="text-amber-500" weight="fill" />
            Staff Performance
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Track response times, resolution rates & agent activity</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[130px] h-8 text-xs" data-testid="period-selector">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="14">Last 14 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <button
            onClick={fetchData}
            className="h-8 w-8 flex items-center justify-center rounded-lg border border-stone-200 hover:bg-stone-50 transition-colors"
            data-testid="refresh-perf-btn"
          >
            <ArrowsClockwise size={14} className="text-stone-500" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <ArrowsClockwise size={24} className="text-stone-400 animate-spin" />
        </div>
      ) : (
        <>
          {/* Team Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="team-summary">
            <MetricCard
              icon={Users} iconColor="text-emerald-600" iconBg="bg-emerald-50"
              label="Active Agents" value={team.total_agents || 0}
              testId="metric-agents"
            />
            <MetricCard
              icon={ChatText} iconColor="text-blue-600" iconBg="bg-blue-50"
              label="Messages Sent" value={team.total_messages || 0}
              sub={`across ${team.total_conversations || 0} conversations`}
              testId="metric-messages"
            />
            <MetricCard
              icon={Clock} iconColor="text-amber-600" iconBg="bg-amber-50"
              label="Avg Response" value={formatResponseTime(team.avg_response_min)}
              testId="metric-response"
            />
            <MetricCard
              icon={CheckCircle} iconColor="text-green-600" iconBg="bg-green-50"
              label="Resolution Rate" value={`${team.team_resolution_rate || 0}%`}
              sub={`${team.total_resolved || 0} resolved`}
              testId="metric-resolution"
            />
            <MetricCard
              icon={TrendUp} iconColor="text-purple-600" iconBg="bg-purple-50"
              label="Conversations" value={team.total_conversations || 0}
              testId="metric-conversations"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Agent Leaderboard */}
            <div className="lg:col-span-2 space-y-3">
              <h2 className="text-sm font-semibold text-stone-700 flex items-center gap-1.5">
                <Trophy size={15} className="text-amber-500" weight="fill" />
                Agent Leaderboard
              </h2>
              {agents.length === 0 ? (
                <div className="bg-white border border-stone-200 rounded-xl p-8 text-center">
                  <Users size={32} className="text-stone-300 mx-auto mb-2" />
                  <p className="text-sm text-stone-500">No staff activity recorded yet</p>
                  <p className="text-xs text-stone-400 mt-1">Performance data appears once agents respond to guest messages</p>
                </div>
              ) : (
                <div className="space-y-2" data-testid="agent-leaderboard">
                  {agents.map((agent, idx) => (
                    <AgentCard
                      key={agent.name}
                      agent={agent}
                      expanded={expandedAgent === idx}
                      onToggle={() => setExpandedAgent(expandedAgent === idx ? null : idx)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Daily Trend */}
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-stone-700 flex items-center gap-1.5">
                <ChartBar size={15} className="text-teal-500" weight="fill" />
                Daily Activity
              </h2>
              <div className="bg-white border border-stone-200 rounded-xl p-4">
                <DailyTrendChart dailyData={data?.daily_trend} agents={agents} />
              </div>

              {/* Top performer highlight */}
              {agents.length > 0 && (
                <div className="bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4" data-testid="top-performer">
                  <div className="flex items-center gap-2 mb-2">
                    <Crown size={16} className="text-amber-500" weight="fill" />
                    <span className="text-xs font-semibold text-amber-700 uppercase tracking-wider">Top Performer</span>
                  </div>
                  <div className="text-lg font-bold text-stone-800">{agents[0].name}</div>
                  <div className="flex items-center gap-3 mt-1.5 text-xs text-stone-600">
                    <span>{agents[0].total_messages} msgs</span>
                    <span>{formatResponseTime(agents[0].avg_response_min)} avg</span>
                    <span>{agents[0].resolution_rate}% resolved</span>
                  </div>
                  <div className="mt-2">
                    <div className="flex justify-between text-[10px] text-stone-500 mb-0.5">
                      <span>Performance Score</span>
                      <span>{agents[0].performance_score}/10</span>
                    </div>
                    <Progress value={agents[0].performance_score * 10} className="h-1.5" />
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
