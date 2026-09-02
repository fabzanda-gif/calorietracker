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
};

export function ActivityMap({
  points,
  activityName = "attività",
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

      const map = L.map(
        containerRef.current,
        {
          zoomControl: true,
          scrollWheelZoom: false,
          attributionControl: true,
        },
      );

      mapRef.current = map;

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

      const coordinates = points.map(
        (point) =>
          [
            point.latitude,
            point.longitude,
          ] as [number, number],
      );

      const route = L.polyline(
        coordinates,
        {
          color: "#ff3d43",
          weight: 5,
          opacity: 0.96,
          lineCap: "round",
          lineJoin: "round",
        },
      ).addTo(map);

      L.polyline(
        coordinates,
        {
          color: "#ffffff",
          weight: 9,
          opacity: 0.55,
          lineCap: "round",
          lineJoin: "round",
        },
      )
        .addTo(map)
        .bringToBack();

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

      if (coordinates.length === 1) {
        map.setView(start, 15);
      } else {
        map.fitBounds(
          route.getBounds(),
          {
            padding: [28, 28],
            maxZoom: 16,
          },
        );
      }

      window.setTimeout(() => {
        map.invalidateSize();
      }, 80);
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
        className={styles.map}
        role="img"
        aria-label={`Mappa del percorso: ${activityName}`}
      />

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
