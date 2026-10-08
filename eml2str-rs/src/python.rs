//! Python-modul: `import eml2str_rs; eml2str_rs.eml2str(msg, ds2=False)` - a tiszta Python eml2str.eml2str() helyett.
//! Ugyanaz a visszateresi ertek (ds2 es nem ures subject eseten (subject, text) tuple, kulonben text) es ugyanazok
//! a kivetel-tipusok (ValueError, UnicodeError...), mint a Python valtozatban. A feldolgozas alatt a GIL el van
//! engedve, igy tobb szalon parhuzamosan futhat.

use pyo3::exceptions::{PyIndexError, PyRecursionError, PyRuntimeError, PyTypeError, PyUnicodeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyString, PyTuple};

fn to_pyerr(name: &'static str) -> PyErr {
    match name {
        "ValueError" => PyValueError::new_err("embedded null character"),
        "UnicodeError" => PyUnicodeError::new_err("eml2str_rs: UnicodeError"),
        "TypeError" => PyTypeError::new_err("eml2str_rs: TypeError"),
        "IndexError" => PyIndexError::new_err("eml2str_rs: IndexError"),
        "RecursionError" => PyRecursionError::new_err("maximum recursion depth exceeded"),
        other => PyRuntimeError::new_err(format!("eml2str_rs: {other}")),
    }
}

/// eml2str(msg: bytes, ds2: bool = False) -> str | tuple[str, str]
#[pyfunction]
#[pyo3(signature = (msg, ds2 = false))]
fn eml2str<'py>(py: Python<'py>, msg: &[u8], ds2: bool) -> PyResult<Bound<'py, PyAny>> {
    let res = py.detach(|| std::panic::catch_unwind(|| crate::eml2str(msg)).unwrap_or(Err("panic")));
    let (subject, text) = res.map_err(to_pyerr)?;
    let text = PyString::new(py, &text);
    if ds2 && !subject.is_empty() {
        Ok(PyTuple::new(py, [PyString::new(py, &subject), text])?.into_any())
    } else {
        Ok(text.into_any())
    }
}

#[pymodule]
fn eml2str_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(eml2str, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
