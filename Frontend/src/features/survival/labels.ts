import { getLang } from '../../shared/i18n/lang';

const flat = (key: string) => key.toLowerCase().replace(/[^a-z0-9]/g, '');

export function humanizeKey(key: string): string {
  const spaced = key
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const RAW_LABELS: Record<string, [ru: string, en: string]> = {
  valid: ['Координаты допустимы', 'Coordinates valid'],
  region: ['Регион', 'Region'],
  latitude: ['Широта, °', 'Latitude, °'],
  longitude: ['Долгота, °', 'Longitude, °'],
  elevation_m: ['Высота рельефа, м', 'Terrain elevation, m'],
  slope_deg: ['Уклон в точке посадки, °', 'Slope at landing point, °'],
  limit_deg: ['Допустимый уклон, °', 'Allowed slope, °'],
  passable: ['Проходимо для ровера', 'Passable for a rover'],
  landing_radius_m: ['Проверенный радиус, м', 'Checked radius, m'],
  safe_radius_m: ['Безопасный радиус, м', 'Safe radius, m'],
  zone_safe: ['Зона посадки безопасна', 'Landing zone is safe'],
  samples: ['Проверено точек', 'Points checked'],
  unsafe_samples: ['Небезопасных точек', 'Unsafe points'],
  min_deg: ['Минимальный уклон, °', 'Minimum slope, °'],
  mean_deg: ['Средний уклон, °', 'Mean slope, °'],
  max_deg: ['Максимальный уклон, °', 'Maximum slope, °'],
  elevation_range_m: ['Перепад высот, м', 'Elevation range, m'],
  sun_elevation_deg: ['Высота Солнца, °', 'Sun elevation, °'],
  insolation_pct: ['Освещённость, % от полной', 'Illumination, % of full'],
  shadowed: ['В тени', 'In shadow'],
  sunlit_hours: ['Часов на свету', 'Hours in sunlight'],
  shadow_hours: ['Часов в тени', 'Hours in shadow'],
  longest_shadow_h: ['Самая долгая тень, ч', 'Longest shadow, h'],
  temp_c: ['Температура, °C', 'Temperature, °C'],
  min_c: ['Минимум, °C', 'Minimum, °C'],
  max_c: ['Максимум, °C', 'Maximum, °C'],
  max_step_c: ['Макс. скачок за час, °C', 'Max. jump per hour, °C'],
  peak_stress_mpa: ['Пиковое напряжение, МПа', 'Peak stress, MPa'],
  peak_risk: ['Уровень риска', 'Risk level'],
  high_risk_intervals: ['Часов с высоким риском', 'High-risk hours'],
  min_soc_pct: ['Минимум заряда, %', 'Minimum charge, %'],
  final_soc_pct: ['Заряд в конце, %', 'Final charge, %'],
  soc_pct: ['Заряд, %', 'Charge, %'],
  generated_wh: ['Выработка, Вт·ч', 'Generation, Wh'],
  consumed_wh: ['Потребление, Вт·ч', 'Consumption, Wh'],
  unserved_wh: ['Нехватка энергии, Вт·ч', 'Energy shortfall, Wh'],
  curtailed_wh: ['Излишек (сброс), Вт·ч', 'Surplus (curtailed), Wh'],
  step_h: ['Шаг, ч', 'Step, h'],
  points: ['Точки', 'Points'],
  hour: ['Час', 'Hour'],
  generation_w: ['Выработка, Вт', 'Generation, W'],
  initial_efficiency_pct: ['КПД панелей в начале, %', 'Panel efficiency at start, %'],
  final_efficiency_pct: ['КПД панелей в конце, %', 'Panel efficiency at end, %'],
  lost_generation_wh: ['Потери выработки, Вт·ч', 'Lost generation, Wh'],
  status: ['Статус', 'Status'],
  search_radius_m: ['Радиус поиска, м', 'Search radius, m'],
  candidates: ['Проверено вариантов', 'Candidates checked'],
  distance_m: ['Расстояние, м', 'Distance, m'],
  bearing_deg: ['Азимут, °', 'Bearing, °'],
  duration_h: ['Длительность, ч', 'Duration, h'],
  panel_power_w: ['Мощность панелей, Вт', 'Panel power, W'],
  systems_w: ['Бортовые системы, Вт', 'Onboard systems, W'],
  heater_w: ['Обогрев в тени, Вт', 'Shade heater, W'],
  capacity_wh: ['Ёмкость батареи, Вт·ч', 'Battery capacity, Wh'],
  initial_soc_pct: ['Начальный заряд, %', 'Initial charge, %'],
  min_allowed_soc_pct: ['Допустимый минимум заряда, %', 'Minimum allowed charge, %'],
  max_slope_deg: ['Допустимый уклон, °', 'Allowed slope, °'],
  peak_index: ['Пиковый индекс', 'Peak index'],
  mean_index: ['Средний индекс', 'Mean index'],
  visible_at_start: ['Земля видна на старте', 'Earth visible at start'],
  available_hours: ['Часов видимости Земли', 'Hours of Earth visibility'],
  windows: ['Окон видимости', 'Visibility windows'],
  min_one_way_s: ['Мин. задержка сигнала в одну сторону, с', 'Min. one-way signal delay, s'],
  max_one_way_s: ['Макс. задержка сигнала в одну сторону, с', 'Max. one-way signal delay, s'],
};

const LABELS: Record<string, [string, string]> = Object.fromEntries(
  Object.entries(RAW_LABELS).map(([key, label]) => [flat(key), label]),
);

export function keyLabel(key: string): string {
  const pair = LABELS[flat(key)];
  return pair ? pair[getLang() === 'en' ? 1 : 0] : humanizeKey(key);
}

export const AXIS_KEYS = new Set(['hour', 'h', 't', 'time', 'index', 'step', 'i']);
