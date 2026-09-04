"use client";

import "leaflet/dist/leaflet.css";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  ActivityRoutePoint,
} from "@/lib/api/activities";

import styles from "./ActivityMap.module.css";

type ActivityMapProps = {
  points: ActivityRoutePoint[];
  activityName?: string;
  compact?: boolean;
};

function routePath(points: ActivityRoutePoint[]): string {
  const width = 600;
  const height = 320;
  const padding = 24;
  const latitudes = points.map((point) => point.latitude);
  const longitudes = points.map((point) => point.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const latRange = Math.max(maxLat - minLat, 0.000001);
  const lonRange = Math.max(maxLon - minLon, 0.000001);

  return points.map((point, index) => {
    const x = padding + ((point.longitude - minLon) / lonRange) * (width - padding * 2);
    const y = height - padding - ((point.latitude - minLat) / latRange) * (height - padding * 2);
    return `${index === 0 ? "M" : "L"} ${x} ${y}`;
  }).join(" ");
}

export function ActivityMap({
  points,
  activityName = "attività",
  compact = false,
}: ActivityMapProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<{
    remove: () => void;
    invalidateSize: () => void;
  } | null>(null);
  const [tilesUnavailable, setTilesUnavailable] =
    useState(false);

  useEffect(() => {
    if (
      !containerRef.current ||
      points.length === 0
    ) {
      return;
    }

    let cancelled = false;

    async function createMap() {
      const L = await import("leaflet");

      if (
        cancelled ||
        !containerRef.current
      ) {
        return;
      }

      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }

      setTilesUnavailable(false);

      const coordinates = points
        .filter(
          (point) =>
            Number.isFinite(point.latitude) &&
            Number.isFinite(point.longitude) &&
            point.latitude >= -90 &&
            point.latitude <= 90 &&
            point.longitude >= -180 &&
            point.longitude <= 180,
        )
        .map(
          (point) =>
            [
              point.latitude,
              point.longitude,
            ] as [number, number],
        );

      if (coordinates.length === 0) {
        setTilesUnavailable(true);
        return;
      }

      const map = L.map(
        containerRef.current,
        {
          zoomControl: true,
          scrollWheelZoom: false,
          attributionControl: true,
        },
      );

      mapRef.current = map;

      /*
       * Leaflet deve avere una vista valida prima di
       * inizializzare correttamente i layer SVG.
       */
      if (coordinates.length === 1) {
        map.setView(coordinates[0], 15);
      } else {
        map.fitBounds(
          L.latLngBounds(coordinates),
          {
            padding: [28, 28],
            maxZoom: 16,
          },
        );
      }

      const tileLayer = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        },
      );

      tileLayer.on("tileerror", () => {
        setTilesUnavailable(true);
      });

      tileLayer.addTo(map);

      /*
       * Ombra prima, percorso sopra.
       * In questo modo non serve bringToBack(), che
       * causava l'eccezione prima del fitBounds.
       */
      L.polyline(
        coordinates,
        {
          color: "#ffffff",
          weight: 9,
          opacity: 0.55,
          lineCap: "round",
          lineJoin: "round",
        },
      ).addTo(map);

      L.polyline(
        coordinates,
        {
          color: "#ff3d43",
          weight: 5,
          opacity: 0.96,
          lineCap: "round",
          lineJoin: "round",
        },
      ).addTo(map);

      const start = coordinates[0];
      const end =
        coordinates[coordinates.length - 1];

      L.circleMarker(
        start,
        {
          radius: 8,
          color: "#ffffff",
          weight: 4,
          fillColor: "#45ca75",
          fillOpacity: 1,
        },
      )
        .addTo(map)
        .bindTooltip(
          `Partenza · ${activityName}`,
        );

      L.circleMarker(
        end,
        {
          radius: 8,
          color: "#ffffff",
          weight: 4,
          fillColor: "#ff3d43",
          fillOpacity: 1,
        },
      )
        .addTo(map)
        .bindTooltip(
          `Arrivo · ${activityName}`,
        );

      window.setTimeout(() => {
        if (!cancelled) {
          map.invalidateSize();

          if (coordinates.length > 1) {
            map.fitBounds(
              L.latLngBounds(coordinates),
              {
                padding: [28, 28],
                maxZoom: 16,
              },
            );
          }
        }
      }, 120);
    }

    void createMap();

    return () => {
      cancelled = true;

      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [activityName, points]);

  if (!points.length) {
    return (
      <div className={styles.empty}>
        <strong>
          Percorso non disponibile
        </strong>
        <span>
          Questa attività non contiene coordinate
          GPS.
        </span>
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      <div
        ref={containerRef}
        className={`${styles.map} ${compact ? styles.compact : ""}`}
        role="img"
        aria-label={`Mappa del percorso: ${activityName}`}
      />

      {tilesUnavailable ? (
        <svg className={styles.fallbackRoute} viewBox="0 0 600 320" aria-label={`Tracciato GPS: ${activityName}`}>
          <path d={routePath(points)} className={styles.routeShadow} />
          <path d={routePath(points)} className={styles.routeLine} />
        </svg>
      ) : null}

      <div className={styles.legend}>
        <span>
          <i className={styles.startDot} />
          Partenza
        </span>

        <span>
          <i className={styles.endDot} />
          Arrivo
        </span>

        {tilesUnavailable ? (
          <small>
            La base geografica non è disponibile;
            il percorso resta visibile.
          </small>
        ) : null}
      </div>
    </div>
  );
}
