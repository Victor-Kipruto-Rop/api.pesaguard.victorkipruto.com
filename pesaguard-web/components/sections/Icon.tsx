import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  DatabaseZap,
  FileCheck2,
  FileText,
  GitBranch,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Terminal,
  Users,
  Webhook,
  type LucideIcon,
} from "lucide-react";
import type { IconKey } from "@/types/content";

/**
 * Content modules are data, so they name an icon by key. This map is the only
 * place that turns a key into a rendered icon, which keeps `content/*` free of
 * JSX and keeps the icon set reviewable in one file.
 */
const iconMap: Record<IconKey, LucideIcon> = {
  reconcile: RefreshCw,
  monitor: Activity,
  shield: ShieldCheck,
  alert: AlertTriangle,
  report: FileText,
  audit: FileCheck2,
  data: DatabaseZap,
  webhook: Webhook,
  lock: LockKeyhole,
  chart: BarChart3,
  clock: Clock,
  users: Users,
  terminal: Terminal,
  check: CheckCircle2,
  flow: GitBranch,
};

export function Icon({ name, size = 18 }: { name: IconKey; size?: number }) {
  const Glyph = iconMap[name];
  return <Glyph aria-hidden="true" size={size} />;
}