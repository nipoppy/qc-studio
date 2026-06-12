"""Niivue viewer configuration and rendering utilities."""
import streamlit as st
from constants import (
    NIIVUE_HEIGHT, VIEW_MODES, OVERLAY_COLORMAPS, DEFAULT_OVERLAY_OPACITY,
    MESSAGES, ERROR_MESSAGES
)
from utils.data_loaders import load_mri_data
from niivue_component import niivue_viewer


class NiivueViewerConfig:
    """Configuration container for Niivue viewer settings."""
    
    def __init__(self, view_mode: str, overlay_colormap: str, 
                 show_crosshair: bool, radiological: bool,
                 show_colorbar: bool, interpolation: bool,
                 show_overlay: bool):
        """Initialize Niivue viewer configuration.
        
        Args:
            view_mode: Viewing perspective (multiplanar, axial, coronal, sagittal, 3d)
            overlay_colormap: Colormap for overlay (grey, cool, warm)
            show_crosshair: Whether to show crosshair
            radiological: Whether to use radiological convention
            show_colorbar: Whether to show colorbar
            interpolation: Whether to use interpolation
            show_overlay: Whether to show overlay image
        """
        self.view_mode = view_mode
        self.overlay_colormap = overlay_colormap
        self.show_crosshair = show_crosshair
        self.radiological = radiological
        self.show_colorbar = show_colorbar
        self.interpolation = interpolation
        self.show_overlay = show_overlay
    
    def to_settings_dict(self) -> dict:
        """Convert to Niivue settings dictionary."""
        return {
            "crosshair": self.show_crosshair,
            "radiological": self.radiological,
            "colorbar": self.show_colorbar,
            "interpolation": self.interpolation
        }
    
    def get_viewer_key(self, participant_id: str = None, session_id: str = None) -> str:
        """Generate unique key for viewer state based on settings and participant context.
        
        Args:
            participant_id: Current participant ID
            session_id: Current session ID
            
        Returns:
            Unique key string including participant/session context
        """
        participant_key = f"_{participant_id}" if participant_id else ""
        session_key = f"_{session_id}" if session_id else ""
        return f"niivue_{self.view_mode}_{self.overlay_colormap}_{self.show_overlay}{participant_key}{session_key}"


class NiivueViewerManager:
    """Manages Niivue viewer rendering and configuration."""
    
    @staticmethod
    def render_controls_panel() -> NiivueViewerConfig:
        """Render Niivue controls panel and return configuration.
        
        Updates session state with new config when user changes settings.
        
        Returns:
            NiivueViewerConfig object with user selections
        """
        st.header(MESSAGES['niivue_controls_header'])
        
        # Get current config from session state for initial values
        current_config = st.session_state.get('niivue_config', None)
        
        # Overlay toggle - at the top for easy access
        show_overlay = st.checkbox(
            MESSAGES['show_overlay_label'], 
            value=current_config.show_overlay if current_config else False
        )
        
        st.divider()
        
        # View mode selection
        view_mode = st.selectbox(
            MESSAGES['view_mode_label'],
            VIEW_MODES,
            index=VIEW_MODES.index(current_config.view_mode) if current_config else 0,
            help="Select the viewing perspective"
        )
        
        # Overlay colormap selection
        overlay_colormap = st.selectbox(
            MESSAGES['overlay_colormap_label'],
            OVERLAY_COLORMAPS,
            index=OVERLAY_COLORMAPS.index(current_config.overlay_colormap) if current_config else 0,
            help="Select the colormap for the overlay"
        )
        
        # Create new config with updated values
        new_config = NiivueViewerConfig(
            view_mode=view_mode,
            overlay_colormap=overlay_colormap,
            show_crosshair=current_config.show_crosshair if current_config else False,
            radiological=current_config.radiological if current_config else False,
            show_colorbar=current_config.show_colorbar if current_config else True,
            interpolation=current_config.interpolation if current_config else True,
            show_overlay=show_overlay
        )
        
        # Save updated config to session state so render_viewer uses it on next rerun
        st.session_state.niivue_config = new_config
        
        return new_config
    
    @staticmethod
    def build_overlay_list(mri_data: dict, config: NiivueViewerConfig) -> list:
        """Build overlay configuration list based on settings.
        
        NOTE: Overlays are ONLY included when the "Show overlay image" checkbox
        is checked in the NiiVue controls panel (config.show_overlay is True).
        
        Args:
            mri_data: MRI data dictionary from load_mri_data()
            config: NiivueViewerConfig with overlay settings
            
        Returns:
            List of overlay configurations for niivue_viewer
            Empty list if "Show overlay image" is unchecked or no overlay data available
        """
        overlays = []
        
        # Only add overlay if checkbox is checked AND overlay data exists
        if config.show_overlay and "overlay_mri_image_bytes" in mri_data:
            overlay_path = mri_data.get("overlay_mri_image_path")
            overlay_name = str(overlay_path.name) if overlay_path else "overlay.nii.gz"
            
            overlays.append({
                "data": mri_data["overlay_mri_image_bytes"],
                "name": overlay_name,
                "colormap": config.overlay_colormap,
                "opacity": DEFAULT_OVERLAY_OPACITY,
            })
        
        return overlays
    
    @staticmethod
    def build_viewer_kwargs(mri_data: dict, config: NiivueViewerConfig, 
                           participant_id: str = None, session_id: str = None) -> dict:
        """Build kwargs dictionary for niivue_viewer component.
        
        The overlays parameter is always included in the returned kwargs.
        However, overlays will only be displayed in the viewer when the
        "Show overlay image" checkbox is checked in the NiiVue controls panel.
        
        Args:
            mri_data: MRI data dictionary from load_mri_data()
            config: NiivueViewerConfig with viewer settings
            participant_id: Current participant ID for unique key generation
            session_id: Current session ID for unique key generation
            
        Returns:
            Dictionary of kwargs for niivue_viewer() with overlays support
            Overlays list will be empty if checkbox is unchecked
        """
        base_mri_image_bytes = mri_data.get("base_mri_image_bytes")
        base_mri_image_path = mri_data.get("base_mri_image_path")
        
        base_mri_name = str(base_mri_image_path.name) if base_mri_image_path else "base_mri.nii"
        settings = config.to_settings_dict()
        # Build overlays list - will be empty if show_overlay checkbox is unchecked
        overlays = NiivueViewerManager.build_overlay_list(mri_data, config)
        
        # Build viewer kwargs following niivue_viewer API
        viewer_kwargs = {
            "nifti_data": base_mri_image_bytes,
            "filename": base_mri_name,
            "height": NIIVUE_HEIGHT,
            "key": config.get_viewer_key(participant_id, session_id),
            "view_mode": config.view_mode,
            "styled": True,
            "settings": settings,
        }
        
        # Always include overlays parameter (may be empty list if checkbox unchecked)
        viewer_kwargs["overlays"] = overlays
        
        return viewer_kwargs
    
    @staticmethod
    @st.fragment()
    def render_viewer(dataset_dir, qc_config, config: NiivueViewerConfig,
                     participant_id: str = None, session_id: str = None):
        """Render Niivue viewer in the main viewing area.
        
        Args:
            dataset_dir: Root dataset directory
            qc_config: QC configuration object
            config: NiivueViewerConfig with viewer settings
            participant_id: Current participant ID
            session_id: Current session ID
        """
        st.header(MESSAGES['niivue_header'])
        
        try:
            # Load MRI data
            mri_data = load_mri_data(dataset_dir, qc_config)
            
            if "base_mri_image_bytes" not in mri_data:
                st.info(ERROR_MESSAGES['base_mri_not_found'])
                return
            
            # Build and render viewer with participant context for unique key
            viewer_kwargs = NiivueViewerManager.build_viewer_kwargs(mri_data, config, 
                                                                    participant_id, session_id)
            niivue_viewer(**viewer_kwargs)
            
        except Exception as e:
            st.error(ERROR_MESSAGES['mri_load_error'].format(error=e))
