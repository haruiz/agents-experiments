"use client";

import { APIProvider, Map, Marker } from "@vis.gl/react-google-maps";

interface GoogleMapThumbnailProps {
  lat: number;
  lng: number;
  zoom?: number;
}

export default function GoogleMap({
  lat,
  lng,
  zoom = 12
}: GoogleMapThumbnailProps) {
  return (
    <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!}>
      <div
        style={{
          width: "200px",
          height: "200px",
          borderRadius: "8px",
          overflow: "hidden"
        }}
      >
        <Map
          defaultZoom={zoom}
          defaultCenter={{ lat, lng }}
          disableDefaultUI={true}
          gestureHandling="none"
          zoomControl={false}
          mapId={undefined}    // Optional, remove or replace with your map style ID
        >
          <Marker position={{ lat, lng }} />
        </Map>
      </div>
    </APIProvider>
  );
}
