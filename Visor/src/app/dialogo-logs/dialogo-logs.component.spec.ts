import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DialogoLogsComponent } from './dialogo-logs.component';

describe('DialogoLogsComponent', () => {
  let component: DialogoLogsComponent;
  let fixture: ComponentFixture<DialogoLogsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DialogoLogsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DialogoLogsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
