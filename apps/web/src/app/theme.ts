/**
 * Single source of visual tokens. CSS reads them through `--cb-*` variables so the theme and
 * styles.css cannot drift. Spacing follows a 4px grid; type is tuned for Traditional Chinese
 * reading (15px/26px body) rather than the 14px/20px Latin defaults of the reference systems.
 */
import { createTheme } from '@mui/material';

export const color = {
  canvas: '#f6f7f6',
  surface: '#ffffff',
  border: '#e1e7e4',
  borderStrong: '#c9d3ce',
  text: '#1b2420',
  textMuted: '#4d5b55',
  accent: '#23615b',
  accentSoft: '#e8f1ef',
  // A distinct "AI layer" for candidate and live content that is not yet formal.
  aiSurface: '#f1f6fb',
  aiBorder: '#c5d6e8',
  aiText: '#1f4e79',
  warnText: '#8a4b00',
  warnSurface: '#fff4e0',
  warnBorder: '#f0d9a8',
} as const;

export const layout = {
  headerHeight: 48,
  fileBarHeight: 56,
  paneHeaderHeight: 44,
  interviewPaneWidth: 'clamp(380px, 36vw, 520px)',
  sourcePanelWidth: 400,
  documentMaxWidth: 840,
} as const;

const cssVariables = {
  '--cb-canvas': color.canvas,
  '--cb-surface': color.surface,
  '--cb-border': color.border,
  '--cb-border-strong': color.borderStrong,
  '--cb-text': color.text,
  '--cb-text-muted': color.textMuted,
  '--cb-accent': color.accent,
  '--cb-accent-soft': color.accentSoft,
  '--cb-ai-surface': color.aiSurface,
  '--cb-ai-border': color.aiBorder,
  '--cb-ai-text': color.aiText,
  '--cb-warn-text': color.warnText,
  '--cb-warn-surface': color.warnSurface,
  '--cb-warn-border': color.warnBorder,
  '--cb-header-h': `${String(layout.headerHeight)}px`,
  '--cb-file-bar-h': `${String(layout.fileBarHeight)}px`,
  '--cb-pane-header-h': `${String(layout.paneHeaderHeight)}px`,
  '--cb-interview-w': layout.interviewPaneWidth,
  '--cb-source-w': `${String(layout.sourcePanelWidth)}px`,
  '--cb-doc-max-w': `${String(layout.documentMaxWidth)}px`,
} as const;

export const theme = createTheme({
  palette: {
    primary: { main: color.accent },
    text: { primary: color.text, secondary: color.textMuted },
    background: { default: color.canvas, paper: color.surface },
    divider: color.border,
  },
  typography: {
    fontFamily:
      '"Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, -apple-system, sans-serif',
    h4: { fontSize: '1.5rem', lineHeight: '2rem', fontWeight: 600 },
    h5: { fontSize: '1.25rem', lineHeight: '1.75rem', fontWeight: 600 },
    h6: { fontSize: '1rem', lineHeight: '1.5rem', fontWeight: 600 },
    subtitle1: { fontSize: '0.9375rem', lineHeight: '1.375rem', fontWeight: 600 },
    subtitle2: { fontSize: '0.8125rem', lineHeight: '1.125rem', fontWeight: 600 },
    body1: { fontSize: '0.9375rem', lineHeight: '1.625rem' },
    body2: { fontSize: '0.8125rem', lineHeight: '1.25rem' },
    caption: { fontSize: '0.75rem', lineHeight: '1rem' },
    button: { textTransform: 'none', fontSize: '0.875rem', lineHeight: '1.25rem', fontWeight: 500 },
  },
  shape: { borderRadius: 8 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ':root': cssVariables,
        body: { backgroundColor: color.canvas, color: color.text },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 6, minHeight: 32 },
        sizeSmall: { minHeight: 28, paddingInline: 8 },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { outlined: { borderColor: color.border } },
    },
    MuiAlert: {
      styleOverrides: { root: { borderRadius: 8, alignItems: 'center', fontSize: '0.875rem' } },
    },
    MuiChip: { styleOverrides: { root: { borderRadius: 6 } } },
    MuiLink: { defaultProps: { underline: 'hover' } },
    MuiTab: { styleOverrides: { root: { minHeight: 44, fontWeight: 600 } } },
  },
});
