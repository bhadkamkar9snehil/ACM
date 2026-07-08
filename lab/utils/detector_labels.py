"""
ACM Detector Human-Readable Labels

Maps detector algorithm codes to user-friendly descriptions for dashboards and reports.
"""

# Detector code to human-readable label mapping
DETECTOR_LABELS = {
    'ar1_z': 'Time-Series Anomaly (AR1)',
    'ar1': 'Time-Series Anomaly (AR1)',
    'pca_spe_z': 'Correlation Break (PCA-SPE)',
    'pca_spe': 'Correlation Break (PCA-SPE)',
    'pca_t2_z': 'Multivariate Outlier (PCA-T2)',
    'pca_t2': 'Multivariate Outlier (PCA-T2)',
    'iforest_z': 'Rare State (IsolationForest)',
    'iforest': 'Rare State (IsolationForest)',
    'gmm_z': 'Density Anomaly (GMM)',
    'gmm': 'Density Anomaly (GMM)',
    'omr_z': 'Baseline Consistency (OMR)',
    'omr': 'Baseline Consistency (OMR)',
    'fused_z': 'Fused Multi-Detector',
    'fused': 'Fused Multi-Detector'
}

# SQL-safe labels (ASCII only, no special chars except spaces/parens/hyphens)
DETECTOR_LABELS_SQL = {
    'ar1_z': 'Time-Series Anomaly (AR1)',
    'ar1': 'Time-Series Anomaly (AR1)',
    'pca_spe_z': 'Correlation Break (PCA-SPE)',
    'pca_spe': 'Correlation Break (PCA-SPE)',
    'pca_t2_z': 'Multivariate Outlier (PCA-T2)',
    'pca_t2': 'Multivariate Outlier (PCA-T2)',
    'iforest_z': 'Rare State (IsolationForest)',
    'iforest': 'Rare State (IsolationForest)',
    'gmm_z': 'Density Anomaly (GMM)',
    'gmm': 'Density Anomaly (GMM)',
    'omr_z': 'Baseline Consistency (OMR)',
    'omr': 'Baseline Consistency (OMR)',
    'fused_z': 'Fused Multi-Detector',
    'fused': 'Fused Multi-Detector'
}

# Short labels for compact displays (dashboard tables)
DETECTOR_LABELS_SHORT = {
    'ar1_z': 'Time-Series (AR1)',
    'ar1': 'Time-Series (AR1)',
    'pca_spe_z': 'Correlation (PCA)',
    'pca_spe': 'Correlation (PCA)',
    'pca_t2_z': 'Outlier (PCA-T²)',
    'pca_t2': 'Outlier (PCA-T²)',
    'iforest_z': 'Rare State (IF)',
    'iforest': 'Rare State (IF)',
    'gmm_z': 'Density (GMM)',
    'gmm': 'Density (GMM)',
    'omr_z': 'Baseline (OMR)',
    'omr': 'Baseline (OMR)',
    'fused_z': 'Fused',
    'fused': 'Fused'
}

# Detailed descriptions for tooltips/documentation
DETECTOR_DESCRIPTIONS = {
    'ar1_z': 'Autoregressive(1) model detecting trend breaks, spikes, and time-series discontinuities in individual sensors',
    'pca_spe_z': 'Principal Component Analysis Squared Prediction Error detecting correlation pattern breaks across sensor groups',
    'pca_t2_z': "Principal Component Analysis Hotelling's T² detecting multivariate outliers in the principal component space",
    'iforest_z': 'Isolation Forest ensemble detecting rare operational states through partition-based anomaly scoring',
    'gmm_z': 'Gaussian Mixture Model detecting density-based anomalies by measuring likelihood under learned distributions',
    'omr_z': 'Overall Model Residual detecting deviations from learned sensor relationships using multivariate regression',
    'fused_z': 'Weighted fusion of all detector scores combining multiple detection algorithms for robust anomaly identification'
}

# Categories for grouping in UI
DETECTOR_CATEGORIES = {
    'ar1_z': 'Univariate',
    'pca_spe_z': 'Multivariate',
    'pca_t2_z': 'Multivariate',
    'iforest_z': 'Ensemble',
    'gmm_z': 'Probabilistic',
    'omr_z': 'Meta-Detector',
    'fused_z': 'Fusion'
}


def get_detector_label(detector_code: str, use_short: bool = False, sql_safe: bool = False) -> str:
    """
    Get human-readable label for detector code.
    
    Args:
        detector_code: Raw detector code (e.g., 'ar1_z', 'pca_spe_z')
        use_short: Use short label for compact displays
        sql_safe: Use SQL-safe label (ASCII only, no Unicode chars like ²)
    
    Returns:
        Human-readable label (e.g., 'Time-Series Anomaly (AR1)')
    
    Examples:
        >>> get_detector_label('gmm_z')
        'Density Anomaly (GMM)'
        
        >>> get_detector_label('ar1_z', use_short=True)
        'Time-Series (AR1)'
        
        >>> get_detector_label('pca_t2_z', sql_safe=True)
        'Multivariate Outlier (PCA-T2)'
    """
    if sql_safe:
        labels = DETECTOR_LABELS_SQL
    elif use_short:
        labels = DETECTOR_LABELS_SHORT
    else:
        labels = DETECTOR_LABELS
    return labels.get(detector_code, detector_code)


def get_detector_description(detector_code: str) -> str:
    """
    Get detailed description for detector code.
    
    Args:
        detector_code: Raw detector code (e.g., 'ar1_z')
    
    Returns:
        Detailed description of what the detector does
    """
    return DETECTOR_DESCRIPTIONS.get(detector_code, 'Unknown detector type')


def format_culprit_label(culprit_string: str, use_short: bool = False) -> str:
    """
    Format culprit string with human-readable detector label.
    
    Handles both simple detector codes and detector+sensor patterns:
    - 'ar1_z' -> 'Time-Series Anomaly (AR1)'
    - 'pca_spe_z(DEMO.SIM.FSAB)' -> 'Correlation Break (PCA-SPE) -> DEMO.SIM.FSAB'
    
    Args:
        culprit_string: Original culprit string from episodes
        use_short: Use short labels for compact displays
    
    Returns:
        Formatted human-readable string
    
    Examples:
        >>> format_culprit_label('gmm_z')
        'Density Anomaly (GMM)'
        
        >>> format_culprit_label('pca_spe_z(Temperature_01)')
        'Correlation Break (PCA-SPE) -> Temperature_01'
        
        >>> format_culprit_label('ar1_z', use_short=True)
        'Time-Series (AR1)'
    """
    if not culprit_string or culprit_string == 'unknown':
        return 'Unknown'
    
    # Check if sensor attribution exists
    if '(' in culprit_string and ')' in culprit_string:
        # Extract detector and sensor
        detector_code = culprit_string[:culprit_string.index('(')]
        sensor = culprit_string[culprit_string.index('(')+1:culprit_string.index(')')]
        
        detector_label = get_detector_label(detector_code, use_short)
        return f"{detector_label} -> {sensor}"
    else:
        # Just detector code
        return get_detector_label(culprit_string, use_short)


def parse_and_label_culprits(culprit_string: str, use_short: bool = False) -> list:
    """
    Parse comma-separated culprits and return labeled list.
    
    Args:
        culprit_string: Comma-separated culprit codes
        use_short: Use short labels
    
    Returns:
        List of formatted culprit labels
    
    Examples:
        >>> parse_and_label_culprits('ar1_z,gmm_z')
        ['Time-Series Anomaly (AR1)', 'Density Anomaly (GMM)']
        
        >>> parse_and_label_culprits('pca_spe_z(Sensor1),iforest_z')
        ['Correlation Break (PCA-SPE) -> Sensor1', 'Rare State (IsolationForest)']
    """
    if not culprit_string:
        return []
    
    culprits = [c.strip() for c in culprit_string.split(',')]
    return [format_culprit_label(c, use_short) for c in culprits]
