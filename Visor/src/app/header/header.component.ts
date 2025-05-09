import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [
    CommonModule,
    MatSlideToggleModule
  ],
  templateUrl: './header.component.html',
  styleUrl: './header.component.css'
})
export class HeaderComponent {
  appName: string = 'Visor';
  @Input() modo: string = '';

  @Input() mostrarCapacidades: boolean = false;
  @Output() mostrarCapacidadesChange = new EventEmitter<boolean>();
  
  constructor() {}

  onToggleChange(event: any) {
    this.mostrarCapacidadesChange.emit(event.checked);
  }

}