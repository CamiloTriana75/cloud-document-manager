import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  ElementRef,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';

import { PageVisibilityService } from '../../../core/browser/page-visibility.service';
import type { CoilRenderer } from './coil-renderer';

type CoilState = 'idle' | 'fallback' | 'live';

function supportsWebGL2(): boolean {
  if (typeof WebGL2RenderingContext === 'undefined') {
    return false;
  }
  try {
    const probe = document.createElement('canvas').getContext('webgl2');
    probe?.getExtension('WEBGL_lose_context')?.loseContext();
    return probe !== null;
  } catch {
    return false;
  }
}

function isLowEndDevice(): boolean {
  const nav = navigator as Navigator & { deviceMemory?: number };
  return (nav.hardwareConcurrency ?? 8) <= 2 || (nav.deviceMemory ?? 8) <= 2;
}

/**
 * Escena decorativa del hero: bobina 3D de anillos teal girando lentamente.
 * three.js se importa bajo demanda tras el primer render; sin WebGL2, en equipos modestos
 * o si falla la carga, queda un fondo CSS. Se pausa fuera de pantalla y con la pestaña oculta;
 * con prefers-reduced-motion dibuja un único fotograma.
 */
@Component({
  selector: 'app-coil-scene',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    'aria-hidden': 'true',
    '[attr.data-state]': 'state()',
    '[attr.data-variant]': 'variant()',
  },
  template: `
    <div class="coil-fallback"></div>
    <canvas #canvas class="coil-canvas"></canvas>
  `,
  styles: `
    :host {
      position: relative;
      display: block;
      pointer-events: none;
      user-select: none;
    }
    .coil-canvas,
    .coil-fallback {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      transition: opacity 900ms var(--ease-out);
    }
    .coil-canvas {
      opacity: 0;
    }
    :host([data-state='live']) .coil-canvas {
      opacity: 1;
    }
    :host([data-state='live']) .coil-fallback {
      opacity: 0;
    }
    .coil-fallback {
      background:
        radial-gradient(
          circle at 50% 64%,
          transparent 0 31%,
          rgba(70, 147, 133, 0.38) 33.5%,
          rgba(70, 147, 133, 0.16) 39%,
          transparent 46%
        ),
        radial-gradient(55% 45% at 50% 58%, rgba(70, 147, 133, 0.16), transparent 72%);
      mask-image: linear-gradient(to bottom, #000 58%, transparent 92%);
    }
  `,
})
export class CoilSceneComponent {
  readonly variant = input<'hero' | 'ambient'>('hero');

  protected readonly state = signal<CoilState>('idle');

  private readonly host: HTMLElement = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly visibility = inject(PageVisibilityService);
  private readonly inView = signal(true);

  private renderer: CoilRenderer | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private intersectionObserver: IntersectionObserver | null = null;
  private destroyed = false;

  constructor() {
    afterNextRender(() => void this.init());

    effect(() => {
      const shouldRun = this.state() === 'live' && this.visibility.visible() && this.inView();
      if (!this.renderer) {
        return;
      }
      if (shouldRun) {
        this.renderer.start();
      } else {
        this.renderer.stop();
      }
    });

    inject(DestroyRef).onDestroy(() => {
      this.destroyed = true;
      this.resizeObserver?.disconnect();
      this.intersectionObserver?.disconnect();
      this.renderer?.dispose();
      this.renderer = null;
    });
  }

  private async init(): Promise<void> {
    if (!supportsWebGL2() || isLowEndDevice()) {
      this.state.set('fallback');
      return;
    }
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    const compact = window.innerWidth < 720;
    try {
      const { createCoilRenderer } = await import('./coil-renderer');
      if (this.destroyed) {
        return;
      }
      const renderer = createCoilRenderer(this.canvas().nativeElement, {
        ringCount: compact ? 22 : 32,
        maxPixelRatio: compact ? 1.25 : 1.75,
        animate: !reduceMotion,
      });
      this.renderer = renderer;
      const { width, height } = this.host.getBoundingClientRect();
      renderer.resize(width, height);

      this.resizeObserver = new ResizeObserver(([entry]) =>
        renderer.resize(entry.contentRect.width, entry.contentRect.height),
      );
      this.resizeObserver.observe(this.host);
      this.intersectionObserver = new IntersectionObserver(([entry]) =>
        this.inView.set(entry.isIntersecting),
      );
      this.intersectionObserver.observe(this.host);

      this.state.set('live');
    } catch {
      this.state.set('fallback');
    }
  }
}
