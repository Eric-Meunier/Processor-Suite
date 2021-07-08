for %%f in (*.ui) do (
          pyuic5 "%%~nf.ui" -o "%%~nf.py"
		  echo %%f
)

