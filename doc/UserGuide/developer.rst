*****************
Developer's Guide
*****************
.. currentmodule:: Stoner.Core
This section provides some notes and guidance on extending the Stoner Package.

Adding New Data File Types
==========================

The first question to ask is whether the data file format that you are working with is one that others in the group will be interested in using. If so, then the best thing would be to include it in the \textbf{fileFormats} module in the package, otherwise you should just write the class in your own script files. In either case, develop the class in your own script files first.

The best way to implement handling a new data format is to write a new subclass of :py:class:`DataFile`::
    class NewInstrumentFile(DataFile):
        """Extends DataFile to load files from somewhere else
    
        Written by Gavin Burnell 11/3/2012"""
     \end{lstlisting}
     A document string should be provided that will help the user identify the function of the new class (and avoid using names that might be commonly replicated !). Only one method needs to be implemented: a new \textit{load}method. The \textit{load} method should have the following structure:
    \begin{lstlisting}
          def load(self,filename=None,*args):
            """Just call the parent class but with the right parameters set"""
            if filename is None or not filename:
                self.get_filename('r')
            else:
                self.filename = filename

then follows the code to actually read the file. It **must** at the very least provide a column header for 
every column of data and read in as much numeric data as possible and it **should** read as 
much of the meta data as possible. The function terminates by returning a copy of the current object::

    return self

One useful function for reading metadata from files is \textit{self.metadata.string\_to\_type()} which will try to convert a string representation of data into a sensible Python type.

There is one class attribute, :py:attr:`DataFile.priority` that can be used to tweak the automatic file 
importing code.::

      self.priority=32

When the subclasses are tried to see if they can load an undetermined file, they are tried in order of 
priority. If your load code can make a positive determination that it has the correct file 
(eg by looking for some magic combination of characters at the start of the file) and can throw an 
exception if it tries loading an incorrect file, then you can give it a lower priority number to 
force it to run earlier. Conversely if your only way of identifying your own files is seeing they make 
sense when you try to load them and that you might partially succeed with a file from another system (as 
can happen if you have a tab or comma separated text file), then you should raise the priority number. 
Currently Lpy:class:`DataFile` defaults to 32, :py:class:`Stoner.FileFormats.CSVFile` and 
:py:class:`Stoner.FileFormats.BigBlueFile` have values of 128 and 64 respectively.

If you need to write any additional methods please make sure that they have Google code-style document 
strings so that the API documentation is picked up correctly.
