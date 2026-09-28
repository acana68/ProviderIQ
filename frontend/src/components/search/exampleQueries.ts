/** Example queries shown as chips under the natural-language box. */
export const EXAMPLE_QUERIES = [
  'Find me a highly rated cardiologist near New York with experience treating heart failure',
  'Affordable family doctor in Chicago accepting new patients',
  'Experienced dermatologist for psoriasis within 10 miles of Boston',
  'Closest psychiatrist to Seattle for anxiety',
] as const

/**
 * For the CMS data: New Jersey cities only, and nothing it doesn't publish (conditions,
 * accepting new patients).
 */
export const CMS_EXAMPLE_QUERIES = [
  'Highly rated cardiologist near Newark',
  'Experienced dermatologist within 10 miles of Jersey City',
  'Primary care doctor in Trenton',
  'Closest psychiatrist to Hackensack',
] as const
