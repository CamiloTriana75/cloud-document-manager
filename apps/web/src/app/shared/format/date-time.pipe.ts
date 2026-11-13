import { Pipe, PipeTransform } from '@angular/core';

import { formatDateTime } from './format-date';

@Pipe({ name: 'dateTime' })
export class DateTimePipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return value ? formatDateTime(value) : '';
  }
}
