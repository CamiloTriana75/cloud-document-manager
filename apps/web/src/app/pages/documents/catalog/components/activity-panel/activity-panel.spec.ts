import { TestBed } from '@angular/core/testing';
import { describe, expect, it, vi } from 'vitest';

import { UploadQueueItem } from '../../../../../core/documents/upload-queue.service';
import { testDocument } from '../test-documents';
import { ActivityPanelComponent } from './activity-panel';

function upload(progress: number): UploadQueueItem {
  return {
    id: 'upload-1',
    workspaceId: 'ws-1',
    file: new File(['x'], 'nuevo.pdf'),
    phase: 'uploading',
    progress,
    loadedBytes: 1,
    error: null,
    documentId: null,
    documentStatus: null,
  };
}

function setup(inputs: Record<string, unknown>) {
  const fixture = TestBed.createComponent(ActivityPanelComponent);
  for (const [key, value] of Object.entries(inputs)) {
    fixture.componentRef.setInput(key, value);
  }
  fixture.detectChanges();
  return { fixture, host: fixture.nativeElement as HTMLElement };
}

describe('ActivityPanelComponent', () => {
  it('muestra los documentos recientes con su estado y los abre al hacer clic', () => {
    const doc = testDocument('a', 'PROCESSING', { original_filename: 'contrato.pdf' });
    const { fixture, host } = setup({ recent: [doc] });
    const spy = vi.fn();
    fixture.componentInstance.openDocument.subscribe(spy);

    expect(host.querySelector('h2')?.textContent).toContain('Actividad');
    expect(host.querySelector('.doc-status-processing')).toBeTruthy();
    const name = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('contrato.pdf'),
    );
    name?.click();
    expect(spy).toHaveBeenCalledWith(doc);
  });

  it('muestra el progreso de las cargas en curso', () => {
    const { host } = setup({ recent: [], uploads: [upload(42)] });
    const bar = host.querySelector('[role="progressbar"]');

    expect(host.textContent).toContain('nuevo.pdf');
    expect(bar?.getAttribute('aria-valuenow')).toBe('42');
  });

  it('solo ofrece la zona para soltar archivos a quien puede subir', () => {
    expect(setup({ recent: [], canUpload: false }).host.querySelector('.dropbar')).toBeNull();

    const { fixture, host } = setup({ recent: [], canUpload: true });
    const spy = vi.fn();
    fixture.componentInstance.filesDropped.subscribe(spy);
    const dropbar = host.querySelector('.dropbar') as HTMLElement;
    const file = new File(['x'], 'arrastrado.pdf');
    const drop = new Event('drop', { bubbles: true, cancelable: true });
    Object.defineProperty(drop, 'dataTransfer', { value: { files: [file] } });
    dropbar.dispatchEvent(drop);

    expect(host.querySelector('button[aria-label="Seleccionar archivos para subir"]')).toBeTruthy();
    expect(spy).toHaveBeenCalledWith([file]);
  });

  it('explica cuando no hay actividad', () => {
    expect(setup({ recent: [] }).host.textContent).toContain('Sin actividad todavía');
  });
});
