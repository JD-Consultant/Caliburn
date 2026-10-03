/**
 * Single source of visual tokens. CSS reads them through `--cb-*` variables so the theme and
 * styles.css cannot drift. Direction, sources and measured values: docs/research/engineering/
 * 2026-10-02-web-ui-benchmark-and-direction.md ("warm paper" surfaces, hairline alpha borders,
 * very low layered shadows, CJK-first type). Spacing sits on a 4px grid.
 *
 * Alpha layers derive from one ink color, so borders and hover tints keep the same hue on any
 * surface (Linear, Geist and Notion all do this). Colors given to MUI use the comma syntax
 * because its color utilities cannot parse the space-separated form.
 */
import { createElement } from 'react';
import { createTheme } from '@mui/material';
import type { Components, Theme } from '@mui/material';
import { CheckCircleIcon, ErrorIcon, InfoIcon, WarningIcon } from '../shared/ui/icons';

const inkChannels = '33, 32, 28'; // #21201c, a warm near-black
const accentChannels = '35, 97, 91'; // #23615b, the brand jade
const tint = (channels: string, alpha: number) => `rgba(${channels}, ${String(alpha)})`;
const ink = (alpha: number) => tint(inkChannels, alpha);
const accentTint = (alpha: number) => tint(accentChannels, alpha);

export const color = {
  canvas: '#f6f5f4',
  surface: '#ffffff',
  /** Text and icons on a solid accent, AI or warning fill. */
  onAccent: '#ffffff',
  text: '#21201c',
  /** 6.0:1 on surface, 5.6:1 on canvas. The next step up (#82827c) fails AA for text. */
  textMuted: '#63635e',
  /** Icons and disabled glyphs only: 3.9:1 on surface does not pass for text. */
  textFaint: '#82827c',
  hover: ink(0.04),
  pressed: ink(0.07),
  borderSubtle: ink(0.06),
  border: ink(0.1),
  borderStrong: ink(0.18),
  /** 3.3:1 on surface, the lightest warm gray that meets WCAG 1.4.11 for a field boundary. */
  borderControl: '#8d8d86',
  // Brand jade (#23615b is the unchanged brand color); the ramp keeps its hue in OKLCH.
  accent: '#23615b',
  accentHover: '#13504a',
  accentSoft: '#e8f1f0',
  accentSoftHover: '#dfebe9',
  accentSoftActive: '#d4e3e1',
  accentBorder: '#a9c5c1',
  accentText: '#134742',
  focus: '#23615b',
  // "AI layer": candidate and live content that is not formal yet (Radix indigo steps).
  aiSurface: '#f7f9ff',
  aiSoft: '#edf2fe',
  aiBorder: '#d2deff',
  aiBorderStrong: '#abbdf9',
  aiSolid: '#3a5bc7',
  aiText: '#1f2d5c',
  // Semantic soft chips: tinted surface, matching border, dark text (all >= 4.5:1).
  warnSurface: '#fefbe9',
  warnSoft: '#fff7c2',
  warnBorder: '#f3d673',
  warnText: '#4f3422',
  warnIcon: '#ab6400',
  dangerSurface: '#fff7f7',
  dangerSoft: '#feebec',
  dangerBorder: '#fdbdbe',
  dangerText: '#641723',
  dangerIcon: '#ce2c31',
  okSurface: '#f4fbf6',
  okSoft: '#e6f6eb',
  okBorder: '#adddc0',
  okText: '#193b2d',
  okIcon: '#218358',
} as const;

export const radius = { sm: 6, md: 8, lg: 12, xl: 16, xxl: 24 } as const;

/** Geist-style: an edge ring plus several very faint blurs instead of one heavy shadow. */
export const shadow = {
  xs: `0 1px 2px ${ink(0.04)}`,
  sm: `0 0 0 1px ${ink(0.08)}, 0 1px 2px ${ink(0.04)}`,
  md: `0 0 0 1px ${ink(0.08)}, 0 1px 1px ${ink(0.02)}, 0 4px 8px -4px ${ink(0.04)}, 0 16px 24px -8px ${ink(0.06)}`,
  lg: `0 0 0 1px ${ink(0.08)}, 0 1px 1px ${ink(0.02)}, 0 8px 16px -4px ${ink(0.04)}, 0 24px 32px -8px ${ink(0.06)}`,
  /**
   * The chat composer keeps ChatGPT's structure (an edge ring, a close blur, a wide faint glow); the
   * ring is 12% where theirs is 4%, so the field stays easy to find on a white dock.
   */
  composer: `0 0 0 1px ${ink(0.12)}, 0 2px 8px ${ink(0.04)}, 0 4px 40px 4px ${ink(0.03)}`,
  composerHover: `0 0 0 1px ${ink(0.22)}, 0 2px 8px ${ink(0.04)}, 0 4px 40px 4px ${ink(0.03)}`,
  composerFocus: `0 0 0 1.5px ${color.accent}, 0 0 0 5px ${accentTint(0.14)}, 0 2px 8px ${ink(0.04)}`,
  /** The source sheet's left edge while it overlaps the JD pane. */
  sheet: `-16px 0 32px -8px ${ink(0.08)}`,
} as const;

export const layout = {
  headerHeight: 48,
  paneHeaderHeight: 44,
  interviewPaneWidth: 'clamp(380px, 36vw, 520px)',
  sourcePanelWidth: 400,
  documentMaxWidth: 760,
  /** W3C clreq: horizontal body copy should not exceed 48 characters. `em`, not `ch`: `ch` is the narrow "0". */
  measure: '48em',
  toolbarWidth: 112,
} as const;

/**
 * State changes sit at 120-200ms with a decelerating curve (measured on Linear, Vercel, Notion and
 * Claude). A panel that travels uses the longer-tailed curve Linear and Vercel both ship.
 */
const motion = {
  ease: 'cubic-bezier(0.2, 0, 0, 1)',
  fast: '120ms',
  base: '180ms',
  sheetEase: 'cubic-bezier(0.32, 0.72, 0, 1)',
  sheet: '200ms',
} as const;

const fontSans =
  '"Inter Variable", "Noto Sans TC Variable", "PingFang TC", "Microsoft JhengHei", system-ui, -apple-system, "Segoe UI", sans-serif';

const fontMono =
  'ui-monospace, "Cascadia Code", "SF Mono", Consolas, "Noto Sans TC Variable", monospace';

const cssVariables = {
  '--cb-font-sans': fontSans,
  '--cb-font-mono': fontMono,
  '--cb-canvas': color.canvas,
  '--cb-surface': color.surface,
  '--cb-on-accent': color.onAccent,
  '--cb-text': color.text,
  '--cb-text-muted': color.textMuted,
  '--cb-text-faint': color.textFaint,
  '--cb-hover': color.hover,
  '--cb-pressed': color.pressed,
  '--cb-border-subtle': color.borderSubtle,
  '--cb-border': color.border,
  '--cb-border-strong': color.borderStrong,
  '--cb-border-control': color.borderControl,
  '--cb-accent': color.accent,
  '--cb-accent-hover': color.accentHover,
  '--cb-accent-soft': color.accentSoft,
  '--cb-accent-soft-hover': color.accentSoftHover,
  '--cb-accent-border': color.accentBorder,
  '--cb-accent-text': color.accentText,
  '--cb-focus': color.focus,
  '--cb-ai-surface': color.aiSurface,
  '--cb-ai-soft': color.aiSoft,
  '--cb-ai-border': color.aiBorder,
  '--cb-ai-border-strong': color.aiBorderStrong,
  '--cb-ai-solid': color.aiSolid,
  '--cb-ai-text': color.aiText,
  '--cb-warn-surface': color.warnSurface,
  '--cb-warn-soft': color.warnSoft,
  '--cb-warn-border': color.warnBorder,
  '--cb-warn-text': color.warnText,
  '--cb-warn-icon': color.warnIcon,
  '--cb-ok-soft': color.okSoft,
  '--cb-ok-text': color.okText,
  '--cb-danger-soft': color.dangerSoft,
  '--cb-danger-border': color.dangerBorder,
  '--cb-danger-text': color.dangerText,
  '--cb-danger-icon': color.dangerIcon,
  '--cb-radius-sm': `${String(radius.sm)}px`,
  '--cb-radius-md': `${String(radius.md)}px`,
  '--cb-radius-lg': `${String(radius.lg)}px`,
  '--cb-radius-xl': `${String(radius.xl)}px`,
  '--cb-radius-2xl': `${String(radius.xxl)}px`,
  '--cb-shadow-xs': shadow.xs,
  '--cb-shadow-sm': shadow.sm,
  '--cb-shadow-md': shadow.md,
  '--cb-shadow-lg': shadow.lg,
  '--cb-shadow-composer': shadow.composer,
  '--cb-shadow-composer-hover': shadow.composerHover,
  '--cb-shadow-composer-focus': shadow.composerFocus,
  '--cb-shadow-sheet': shadow.sheet,
  '--cb-ease': motion.ease,
  '--cb-dur-fast': motion.fast,
  '--cb-dur': motion.base,
  '--cb-ease-sheet': motion.sheetEase,
  '--cb-dur-sheet': motion.sheet,
  '--cb-header-h': `${String(layout.headerHeight)}px`,
  '--cb-pane-header-h': `${String(layout.paneHeaderHeight)}px`,
  '--cb-interview-w': layout.interviewPaneWidth,
  '--cb-source-w': `${String(layout.sourcePanelWidth)}px`,
  '--cb-doc-max-w': `${String(layout.documentMaxWidth)}px`,
  '--cb-measure': layout.measure,
  '--cb-toolbar-w': `${String(layout.toolbarWidth)}px`,
} as const;

type SoftTone = { surface: string; border: string; text: string; icon: string };
const tones: Record<'info' | 'warning' | 'error' | 'success', SoftTone> = {
  info: {
    surface: color.aiSurface,
    border: color.aiBorder,
    text: color.aiText,
    icon: color.aiSolid,
  },
  warning: {
    surface: color.warnSurface,
    border: color.warnBorder,
    text: color.warnText,
    icon: color.warnIcon,
  },
  error: {
    surface: color.dangerSurface,
    border: color.dangerBorder,
    text: color.dangerText,
    icon: color.dangerIcon,
  },
  success: {
    surface: color.okSurface,
    border: color.okBorder,
    text: color.okText,
    icon: color.okIcon,
  },
};

const focusOutline = { outline: `2px solid ${color.focus}`, outlineOffset: 2 } as const;
const transition = (...props: string[]) =>
  props.map((p) => `${p} ${motion.fast} ${motion.ease}`).join(', ');

const components: Components<Theme> = {
  MuiCssBaseline: {
    styleOverrides: {
      ':root': cssVariables,
      html: { colorScheme: 'light', WebkitTextSizeAdjust: '100%' },
      body: {
        backgroundColor: color.canvas,
        color: color.text,
        WebkitFontSmoothing: 'antialiased',
        MozOsxFontSmoothing: 'grayscale',
        textRendering: 'optimizeLegibility',
      },
      '::selection': { backgroundColor: accentTint(0.2) },
      // Thin, translucent scrollbars: the default Windows ones are heavy next to hairline borders.
      '*': { scrollbarWidth: 'thin', scrollbarColor: `${ink(0.28)} transparent` },
    },
  },
  MuiButtonBase: { defaultProps: { disableRipple: true } },
  MuiButton: {
    defaultProps: { disableElevation: true },
    styleOverrides: {
      root: {
        minHeight: 36,
        padding: '6px 14px',
        borderRadius: radius.md,
        transition: transition('background-color', 'border-color', 'color', 'box-shadow'),
        '&.Mui-focusVisible': focusOutline,
      },
      sizeSmall: {
        minHeight: 28,
        padding: '2px 10px',
        fontSize: '0.8125rem',
        borderRadius: radius.sm,
      },
      sizeLarge: { minHeight: 44, padding: '10px 18px' },
      startIcon: { marginRight: 6, marginLeft: -2, '& > *:nth-of-type(1)': { fontSize: 18 } },
      outlined: {
        backgroundColor: color.surface,
        '&.Mui-disabled': { borderColor: color.borderSubtle, color: ink(0.38) },
      },
      text: { '&.Mui-disabled': { color: ink(0.38) } },
    },
    variants: [
      {
        props: { variant: 'contained', color: 'primary' },
        style: {
          backgroundColor: color.accent,
          color: color.onAccent,
          '&:hover': { backgroundColor: color.accentHover },
          '&.Mui-disabled': { backgroundColor: color.pressed, color: ink(0.38) },
        },
      },
      {
        props: { variant: 'outlined', color: 'primary' },
        style: {
          borderColor: color.borderStrong,
          color: color.text,
          '&:hover': { backgroundColor: color.hover, borderColor: color.borderStrong },
        },
      },
      {
        props: { variant: 'text', color: 'primary' },
        style: { color: color.accent, '&:hover': { backgroundColor: color.accentSoft } },
      },
    ],
  },
  MuiIconButton: {
    styleOverrides: {
      root: {
        color: color.textMuted,
        borderRadius: radius.sm,
        transition: transition('background-color', 'color'),
        '&:hover': { backgroundColor: color.hover, color: color.text },
        '&.Mui-focusVisible': focusOutline,
      },
      sizeSmall: { width: 28, height: 28, padding: 0, fontSize: '1.125rem' },
      colorError: {
        color: color.textMuted,
        '&:hover': { backgroundColor: color.dangerSoft, color: color.dangerIcon },
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        height: 24,
        borderRadius: radius.sm,
        fontSize: '0.75rem',
        fontWeight: 500,
        lineHeight: '1rem',
      },
      label: { paddingInline: 8 },
      outlined: { borderColor: color.borderStrong },
      sizeSmall: { height: 24 },
      colorInfo: {
        backgroundColor: tones.info.surface,
        borderColor: tones.info.border,
        color: tones.info.text,
      },
      colorWarning: {
        backgroundColor: color.warnSoft,
        borderColor: color.warnBorder,
        color: color.warnText,
      },
      colorError: {
        backgroundColor: tones.error.surface,
        borderColor: tones.error.border,
        color: tones.error.text,
      },
      colorSuccess: {
        backgroundColor: tones.success.surface,
        borderColor: tones.success.border,
        color: tones.success.text,
      },
    },
  },
  MuiAlert: {
    defaultProps: {
      variant: 'standard',
      iconMapping: {
        info: createElement(InfoIcon),
        success: createElement(CheckCircleIcon),
        warning: createElement(WarningIcon),
        error: createElement(ErrorIcon),
      },
    },
    styleOverrides: {
      root: ({ ownerState }) => {
        const tone = tones[ownerState.severity ?? 'info'];
        return {
          alignItems: 'flex-start',
          padding: '8px 12px',
          borderRadius: radius.md,
          border: `1px solid ${tone.border}`,
          backgroundColor: tone.surface,
          color: tone.text,
          fontSize: '0.8125rem',
          lineHeight: '1.25rem',
        };
      },
      icon: ({ ownerState }) => ({
        padding: '2px 0',
        marginRight: 8,
        opacity: 1,
        fontSize: 18,
        color: tones[ownerState.severity ?? 'info'].icon,
      }),
      message: { padding: '2px 0' },
      action: { padding: '0 0 0 12px', marginRight: -4, alignItems: 'center' },
    },
  },
  MuiPaper: {
    defaultProps: { elevation: 0 },
    styleOverrides: {
      root: { backgroundImage: 'none' },
      outlined: { borderColor: color.border, borderRadius: radius.lg },
    },
  },
  MuiDivider: { styleOverrides: { root: { borderColor: color.border } } },
  MuiLink: {
    defaultProps: { underline: 'hover' },
    styleOverrides: { root: { color: color.accent, '&.Mui-focusVisible': focusOutline } },
  },
  MuiTextField: { defaultProps: { variant: 'outlined' } },
  // Labels sit above the field (NN/g, GOV.UK, Linear, Stripe): a floating label shrinks to 12px,
  // too small for Chinese, and its notch cuts the border.
  MuiInputLabel: {
    styleOverrides: {
      root: {
        position: 'static',
        transform: 'none',
        maxWidth: '100%',
        marginBottom: 6,
        color: color.text,
        fontSize: '0.8125rem',
        lineHeight: '1.25rem',
        fontWeight: 500,
        '&.Mui-focused': { color: color.text },
        '&.Mui-error': { color: color.text },
        '&.Mui-disabled': { color: color.textMuted },
      },
      asterisk: { color: color.dangerIcon },
    },
  },
  MuiFormControl: { styleOverrides: { root: { '& > .MuiInputBase-root': { marginTop: 0 } } } },
  MuiOutlinedInput: {
    styleOverrides: {
      root: {
        borderRadius: radius.md,
        backgroundColor: color.surface,
        fontSize: '0.9375rem',
        '& .MuiOutlinedInput-notchedOutline': {
          top: 0,
          borderColor: color.borderControl,
          transition: transition('border-color', 'box-shadow'),
          '& legend': { display: 'none' },
        },
        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: color.text },
        '&.Mui-focused': { boxShadow: `0 0 0 3px ${accentTint(0.18)}` },
        '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
          borderColor: color.accent,
          borderWidth: 1,
        },
        '&.Mui-disabled': { backgroundColor: color.hover },
        '&.Mui-disabled .MuiOutlinedInput-notchedOutline': { borderColor: color.border },
      },
      input: { padding: '10px 12px', lineHeight: '1.25rem', height: 'auto' },
      sizeSmall: { '& .MuiOutlinedInput-input': { padding: '6px 10px' } },
      multiline: { padding: 0 },
    },
  },
  // Helper text starts at the field's edge, in line with the label above it (MUI indents it 14px).
  MuiFormHelperText: {
    styleOverrides: {
      root: {
        marginInline: 0,
        marginBlockStart: 4,
        fontSize: '0.75rem',
        lineHeight: '1rem',
        color: color.textMuted,
      },
    },
  },
  MuiDialog: {
    styleOverrides: {
      // The scrim belongs to dialogs only: menus and pickers use an invisible backdrop.
      root: { '& > .MuiBackdrop-root': { backgroundColor: ink(0.36) } },
      paper: { borderRadius: radius.xl, boxShadow: shadow.lg, border: 0 },
    },
  },
  MuiDialogTitle: {
    styleOverrides: {
      root: {
        padding: '20px 24px 8px',
        fontSize: '1.125rem',
        lineHeight: '1.75rem',
        fontWeight: 600,
      },
    },
  },
  MuiDialogContent: { styleOverrides: { root: { padding: '8px 24px 16px' } } },
  MuiDialogActions: { styleOverrides: { root: { padding: '8px 24px 20px', gap: 8 } } },
  // A long option wraps at 420px instead of stretching the menu past the window (min-width, the
  // anchor's width, still wins for a wide field).
  MuiMenu: {
    styleOverrides: {
      paper: {
        borderRadius: radius.lg,
        boxShadow: shadow.md,
        maxWidth: 'min(420px, calc(100% - 32px))',
      },
    },
  },
  MuiPopover: {
    styleOverrides: {
      paper: {
        borderRadius: radius.lg,
        boxShadow: shadow.md,
        maxWidth: 'min(420px, calc(100% - 32px))',
      },
    },
  },
  MuiMenuItem: {
    styleOverrides: {
      root: {
        minHeight: 36,
        margin: '2px 4px',
        borderRadius: radius.sm,
        fontSize: '0.875rem',
        lineHeight: '1.25rem',
        '&.Mui-selected': { backgroundColor: color.accentSoft },
        '&.Mui-selected:hover': { backgroundColor: color.accentSoftHover },
      },
    },
  },
  MuiTabs: {
    styleOverrides: {
      root: { minHeight: 44 },
      indicator: { height: 2, borderRadius: 2, backgroundColor: color.accent },
    },
  },
  MuiTab: {
    styleOverrides: {
      root: {
        minHeight: 44,
        fontSize: '0.875rem',
        lineHeight: '1.25rem',
        fontWeight: 500,
        color: color.textMuted,
        '&.Mui-selected': { color: color.text },
        '&.Mui-focusVisible': { outlineOffset: -2 },
      },
    },
  },
  // Segmented control: a quiet track with a raised selected segment.
  MuiToggleButtonGroup: {
    styleOverrides: {
      root: { padding: 2, gap: 2, borderRadius: radius.md, backgroundColor: color.pressed },
      grouped: {
        border: 0,
        borderRadius: `${String(radius.sm)}px !important`,
        margin: 0,
      },
    },
  },
  MuiToggleButton: {
    styleOverrides: {
      root: {
        minHeight: 26,
        padding: '2px 10px',
        fontSize: '0.8125rem',
        fontWeight: 500,
        lineHeight: '1.25rem',
        color: color.textMuted,
        '&:hover': { backgroundColor: color.hover },
        '&.Mui-selected': {
          backgroundColor: color.surface,
          color: color.text,
          boxShadow: shadow.sm,
        },
        '&.Mui-selected:hover': { backgroundColor: color.surface },
        '&.Mui-focusVisible': focusOutline,
      },
    },
  },
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        backgroundColor: color.text,
        borderRadius: radius.sm,
        padding: '4px 8px',
        fontSize: '0.75rem',
        lineHeight: '1rem',
        fontWeight: 500,
      },
    },
  },
  MuiSkeleton: { styleOverrides: { root: { backgroundColor: color.borderSubtle } } },
  MuiTableCell: {
    styleOverrides: {
      root: { borderBottom: `1px solid ${color.borderSubtle}`, padding: '12px 16px' },
      head: {
        padding: '10px 16px',
        fontSize: '0.75rem',
        lineHeight: '1rem',
        fontWeight: 500,
        color: color.textMuted,
        borderBottom: `1px solid ${color.border}`,
      },
    },
  },
};

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: color.accent, dark: color.accentHover, contrastText: color.onAccent },
    error: { main: color.dangerIcon, light: color.dangerSoft, contrastText: color.onAccent },
    warning: { main: color.warnIcon, light: color.warnSurface, contrastText: color.onAccent },
    info: { main: color.aiSolid, light: color.aiSoft, contrastText: color.onAccent },
    success: { main: color.okIcon, light: color.okSoft, contrastText: color.onAccent },
    text: { primary: color.text, secondary: color.textMuted, disabled: ink(0.38) },
    background: { default: color.canvas, paper: color.surface },
    divider: color.border,
    action: {
      hover: color.hover,
      selected: color.pressed,
      disabled: ink(0.38),
      disabledBackground: color.pressed,
      focus: color.pressed,
    },
  },
  typography: {
    fontFamily: fontSans,
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 600,
    h4: { fontSize: '1.5rem', lineHeight: '2rem', fontWeight: 600, letterSpacing: '-0.01em' },
    h5: { fontSize: '1.25rem', lineHeight: '1.75rem', fontWeight: 600, letterSpacing: '-0.005em' },
    h6: { fontSize: '1rem', lineHeight: '1.5rem', fontWeight: 600 },
    subtitle1: { fontSize: '0.9375rem', lineHeight: '1.5rem', fontWeight: 600 },
    subtitle2: { fontSize: '0.8125rem', lineHeight: '1.25rem', fontWeight: 600 },
    body1: { fontSize: '0.9375rem', lineHeight: '1.625rem' },
    body2: { fontSize: '0.8125rem', lineHeight: '1.25rem' },
    caption: { fontSize: '0.75rem', lineHeight: '1rem' },
    overline: {
      fontSize: '0.75rem',
      lineHeight: '1rem',
      fontWeight: 500,
      letterSpacing: '0.02em',
      textTransform: 'none',
    },
    button: { textTransform: 'none', fontSize: '0.875rem', lineHeight: '1.25rem', fontWeight: 500 },
  },
  shape: { borderRadius: radius.md },
  components,
});
