import { Pipe, PipeTransform } from '@angular/core';

import { formatRelativeTime } from './format-date';

/** Pipe puro: se recalcula cuando cambia la fecha (los listados se refrescan por polling). */
@Pipe({ name: 'relativeTime' })
export class RelativeTimePipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return value ? formatRelativeTime(value) : '';
  }
}
