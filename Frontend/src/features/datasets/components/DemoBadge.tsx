import { Badge } from '../../../shared/ui/Badge';

export function DemoBadge({ mode }: { mode?: string | undefined }) {
  if (mode === 'final') return null;
  return <Badge tone="demo">DEMO DATA</Badge>;
}
