/**
 * Animation Utilities for Smooth Transitions
 */

import { theme } from "./theme"

export const animations = {
  // Fade animations
  fadeIn: {
    animation: `fadeIn ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  fadeInSlow: {
    animation: `fadeIn ${theme.transitions.duration.slow} ${theme.transitions.timing.easeOut}`,
  },

  // Slide animations
  slideInUp: {
    animation: `slideInUp ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  slideInDown: {
    animation: `slideInDown ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  slideInLeft: {
    animation: `slideInLeft ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  slideInRight: {
    animation: `slideInRight ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  // Scale animations
  scaleIn: {
    animation: `scaleIn ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  // Pulse animation
  pulse: {
    animation: `pulse ${theme.transitions.duration.slower} ${theme.transitions.timing.ease} infinite`,
  },

  // Glow animation
  glow: {
    animation: `glow ${theme.transitions.duration.slowest} ${theme.transitions.timing.ease} infinite`,
  },

  // Float animation
  float: {
    animation: `float ${theme.transitions.duration.slowest} ${theme.transitions.timing.ease} infinite`,
  },

  // Spin animation
  spin: {
    animation: `spin ${theme.transitions.duration.slowest} ${theme.transitions.timing.linear} infinite`,
  },

  // Hover transitions
  hoverTransition: {
    transition: `all ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },

  hoverTransitionSlow: {
    transition: `all ${theme.transitions.duration.slow} ${theme.transitions.timing.easeOut}`,
  },

  // Color transitions
  colorTransition: {
    transition: `color ${theme.transitions.duration.fast} ${theme.transitions.timing.easeOut}`,
  },

  // Transform transitions
  transformTransition: {
    transition: `transform ${theme.transitions.duration.fast} ${theme.transitions.timing.easeOut}`,
  },

  // Shadow transitions
  shadowTransition: {
    transition: `box-shadow ${theme.transitions.duration.fast} ${theme.transitions.timing.easeOut}`,
  },

  // All smooth transitions
  smoothTransition: {
    transition: `all ${theme.transitions.duration.normal} ${theme.transitions.timing.easeOut}`,
  },
}

export type Animations = typeof animations
