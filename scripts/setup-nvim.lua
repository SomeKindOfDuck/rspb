-- Run with the applied configuration and RSPB_NVIM_SETUP=1.
-- Report installation failures to the caller instead of exiting successfully with :qa.
local function setup()
  local lazy = require("lazy")
  local lockfile = vim.fn.stdpath("config") .. "/lazy-lock.json"
  local locked = vim.fn.readfile(lockfile)
  local extensions = vim.g.coc_global_extensions
  assert(type(extensions) == "table" and #extensions > 0, "Missing rspb CoC configuration")
  vim.g.coc_global_extensions = {} -- Install synchronously below, without a second background job.

  local ok, err = pcall(function()
    lazy.install({ wait = true, show = false, lockfile = true })
    assert(not require("lazy.manage.checker").has_errors(), "Neovim plugin installation failed")
  end)
  -- lazy.install may rewrite the lockfile, including the bootstrapped lazy.nvim itself.
  vim.fn.writefile(locked, lockfile)
  -- Reload the saved file, rather than restoring from lazy.install's in-memory snapshot.
  require("lazy.manage.lock")._loaded = false
  assert(ok, err)
  ok, err = pcall(function()
    lazy.restore({ wait = true, show = false })
    assert(not require("lazy.manage.checker").has_errors(), "Neovim plugin restore failed")
  end)
  vim.fn.writefile(locked, lockfile)
  require("lazy.manage.lock")._loaded = false
  assert(ok, err)

  lazy.load({ plugins = { "nvim-treesitter", "coc.nvim" } })
  vim.cmd("TSInstallSync! python lua vim bash c cpp json")
  for _, language in ipairs({ "python", "lua", "vim", "bash", "c", "cpp", "json" }) do
    assert(vim.treesitter.language.add(language), "Missing parser: " .. language)
  end

  vim.fn["coc#rpc#start_server"]()
  assert(vim.wait(30000, function() return vim.fn["coc#rpc#ready"]() == 1 end, 100),
    "CoC did not start; check the Node.js installation")
  vim.cmd("CocInstall -sync " .. table.concat(extensions, " "))
  local extension_dir = vim.fn["coc#util#get_data_home"]() .. "/extensions/node_modules/"
  for _, extension in ipairs(extensions) do
    assert(vim.fn.filereadable(extension_dir .. extension .. "/package.json") == 1,
      "CoC extension installation failed: " .. extension)
  end
end

local ok, err = xpcall(setup, debug.traceback)
if not ok then
  vim.api.nvim_err_writeln(err)
  vim.cmd("cquit 1")
else
  print("Neovim plugins, parsers and CoC extensions are ready.")
  vim.cmd("qa!")
end
