# Unify NVR Camera Sensor

A Home Assistant custom integration that monitors the recording health of cameras connected to a UniFi Protect NVR.

## Problem

UniFi Protect can silently stop recording external (ONVIF) cameras — the timeline goes grey with no alert. This integration detects that condition by periodically checking whether a recent recording snapshot exists for each camera.

## How it works

On every poll, the integration queries the UniFi Protect API for a recording snapshot from a configurable time ago (e.g. 5 minutes). If no snapshot is returned, it means recording has stalled. The integration tracks how long ago the last confirmed recording was, and exposes that as sensors per camera.

## Entities

For each monitored camera:

| Entity | Type | Description |
|---|---|---|
| Recording Gap | Sensor (minutes) | How long ago the last confirmed recording was |
| Last Confirmed Recording | Sensor (timestamp) | Timestamp of the last detected recording |
| Recording Problem | Binary sensor | `on` when the recording gap exceeds the configured threshold |

## Installation

Install via [HACS](https://hacs.xyz) by adding this repository as a custom repository (category: Integration).

## Configuration

Add the integration via **Settings → Devices & Services → Add Integration → Unify NVR Camera Sensor**.

| Field | Description |
|---|---|
| NVR IP address | Local IP of your UniFi Protect NVR |
| Username | Local NVR user (not Ubiquiti cloud account) |
| Password | Password for the local NVR user |
| Cameras to monitor | Select which cameras to track |
| Recording gap threshold | Gap in minutes before the problem sensor turns `on` |
| Poll interval | How often to check (seconds) |

Camera selection and thresholds can be updated later via the **Configure** button on the integration card.

## Use with ha-onvif-restarter

The `Recording Problem` binary sensor pairs well with [ha-onvif-restarter](https://github.com/leonhe97/ha-onvif-restarter): use it as a trigger in an automation to automatically restart a stalled camera.
