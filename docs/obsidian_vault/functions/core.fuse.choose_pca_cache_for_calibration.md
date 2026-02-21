---
type: function
id: core.fuse.choose_pca_cache_for_calibration
module: core.fuse
source: core/fuse.py
line_start: 1434
line_end: 1451
---

# core.fuse.choose_pca_cache_for_calibration

Defined in: [[modules/core.fuse]]

Source: `core/fuse.py:1434`

Kind: `function`

Signature: `choose_pca_cache_for_calibration(pca_train_spe: Optional[np.ndarray], pca_train_t2: Optional[np.ndarray], train_len: int, logger: Any=Console)`

Summary: Return cached PCA scores only when cache length exactly matches train length.
