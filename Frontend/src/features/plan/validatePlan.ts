import { t } from '../../shared/i18n';
import { inDateRange, transitHours } from './dates';
import { DATE_MAX, DATE_MIN } from './defaults';
import type { Plan, PlanErrors } from './types';

export function validatePlan(plan: Plan): PlanErrors {
  const errors: PlanErrors = {};
  const range = () => t('val.range', { min: DATE_MIN, max: DATE_MAX });
  if (!inDateRange(plan.start)) errors.start = t('val.start', { range: range() });
  if (!inDateRange(plan.landing)) errors.landing = t('val.landing', { range: range() });
  if (!errors.start && !errors.landing) {
    const gap = transitHours(plan.start, plan.landing);
    if (gap === null || gap <= 0) errors.landing = t('val.order');
  }
  return errors;
}
