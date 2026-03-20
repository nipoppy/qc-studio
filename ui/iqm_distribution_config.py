
DISTRIBUTION_t1w_GROUPS = {
    "EFC": ["efc"],
    "FBER": ["fber"],
    "CJV": ["cjv"],
    "WM2MAX": ["wm2max"],
    "FWHM": ["fwhm_avg", "fwhm_x", "fwhm_y", "fwhm_z"],
    "SNR": ["snr_csf", "snr_gm", "snr_wm"],
    "SNRD": ["snrd_csf", "snrd_gm", "snrd_wm"],
    "QI": ["qi_1", "qi_2"],
    "INU": ["inu_range", "inu_med"],
    "ICSV": ["icvs_csf", "icvs_gm", "icvs_wm"],
    "RPVE": ["rpve_csf", "rpve_gm", "rpve_wm"],
    "TPM_OVERLAP": [
        "tpm_overlap_csf", "tpm_overlap_gm", "tpm_overlap_wm"
        ],
    "SUMMARY_BG": [
        "summary_bg_mean", "summary_bg_median", "summary_bg_stdv", "summary_bg_mad",
        "summary_bg_k", "summary_bg_p05", "summary_bg_p95"
        ],
    "SUMMARY_CSF": [
        "summary_csf_mean", "summary_csf_median", "summary_csf_stdv", "summary_csf_mad", "summary_csf_k", "summary_csf_p05", "summary_csf_p95"
        ],
    "SUMMARY_GM": [
        "summary_gm_mean", "summary_gm_median", "summary_gm_stdv", "summary_gm_mad", "summary_gm_k", "summary_gm_p05", "summary_gm_p95"
        ],
    "SUMMARY_WM": [
        "summary_wm_mean", "summary_wm_median", "summary_wm_stdv", "summary_wm_mad", "summary_wm_k", "summary_wm_p05", "summary_wm_p95"
        ],
}

DISTRIBUTION_bold_GROUPS = {
    "EFC": ["efc"],
    "FBER": ["fber"],
    "CJV": ["cjv"],
    "SNR": ["snr"],
    "FWHM": ["fwhm_x", "fwhm_y", "fwhm_z"],
    "GSR": ["gsr_x", "gsr_y"],
    "DVARS": ["dvars_nstd", "dvars_std"],
    "DVARSn": ["dvars_vstd"],
    "FD_MEAN": ["fd_mean"],
    "FD_NUM": ["fd_num"],
    "FD_PERC": ["fd_perc"],
    "SPIKES_NUM": ["spikes_num"],
    "DUMMY": ["dummy_trs"],
    "GCOR": ["gcor"],
    "TNSR": ["tnsr"],
    "AOR": ["aor"],
    "AQI": ["aqi"],
    "SUMMARY_BG": [
        "summary_bg_mean", "summary_bg_stdv", "summary_bg_k", "summary_bg_p05", "summary_bg_p95"
        ],
    "SUMMARY_FG": [
        "summary_fg_mean", "summary_fg_stdv", "summary_fg_k", "summary_fg_p05", "summary_fg_p95"
        ],  
}


IQM_DISTRIBUTION_GROUPS = {
    "T1w": DISTRIBUTION_t1w_GROUPS,
    "BOLD": DISTRIBUTION_bold_GROUPS,
}

REFRENCE_DATA_PATHS = {
    "T1w": "../reference_data/group_T1w.tsv",
    "BOLD": "../reference_data/group_BOLD.tsv"}