import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { AppShell } from './AppShell';

test('AppShell renders the title and content', () => {
  render(<AppShell>content</AppShell>);
  expect(screen.getByRole('heading', { name: 'LAST LIGHT' })).toBeDefined();
  expect(screen.getByText('content')).toBeDefined();
});
