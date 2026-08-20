import { Routes } from '@angular/router';
import { generatorRoutes } from './features/generator/generator.routes';

export const routes: Routes = [
  { path: '', children: generatorRoutes },
];
