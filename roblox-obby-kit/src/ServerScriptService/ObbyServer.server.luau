--!strict
-- OBBY KIT (server)
-- Put this Script in ServerScriptService.
-- Workspace setup (folders):
--   Workspace.Checkpoints  -> Parts named "1", "2", "3", ... (stage order)
--   Workspace.KillBricks   -> any Parts that kill on touch
--   Workspace.Coins        -> any Parts that give coins on touch
--   Workspace.Movers       -> Parts with attributes: Offset (Vector3), Duration (number)
--   Workspace.Spinners     -> Parts with attribute: Speed (degrees per second)

local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local TweenService = game:GetService("TweenService")
local RunService = game:GetService("RunService")

local stageStore = DataStoreService:GetDataStore("ObbyStage_v1")

local checkpoints = workspace:WaitForChild("Checkpoints") :: Folder
local killBricks = workspace:WaitForChild("KillBricks") :: Folder
local coins = workspace:WaitForChild("Coins") :: Folder
local movers = workspace:FindFirstChild("Movers")
local spinners = workspace:FindFirstChild("Spinners")

local COIN_VALUE = 5
local COIN_RESPAWN = 10

-- Helper: get the Player who owns a touching part (or nil)
local function playerFromHit(hit: BasePart): (Player?, Humanoid?)
	local character = hit:FindFirstAncestorOfClass("Model")
	if not character then return nil, nil end
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	local player = Players:GetPlayerFromCharacter(character)
	if player and humanoid and humanoid.Health > 0 then
		return player, humanoid
	end
	return nil, nil
end

------------------------------------------------------------------
-- Leaderstats + saving
------------------------------------------------------------------
local function onPlayerAdded(player: Player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local stage = Instance.new("IntValue")
	stage.Name = "Stage"
	stage.Value = 1
	stage.Parent = leaderstats

	local coinStat = Instance.new("IntValue")
	coinStat.Name = "Coins"
	coinStat.Parent = leaderstats

	-- Load saved progress (pcall because DataStores can fail)
	local ok, saved = pcall(function()
		return stageStore:GetAsync(tostring(player.UserId))
	end)
	if ok and typeof(saved) == "table" then
		stage.Value = saved.stage or 1
		coinStat.Value = saved.coins or 0
	elseif not ok then
		warn("Could not load data for", player.Name, saved)
	end

	-- Spawn at the player's current checkpoint
	player.CharacterAdded:Connect(function(character)
		local cp = checkpoints:FindFirstChild(tostring(stage.Value)) :: BasePart?
		if cp then
			local root = character:WaitForChild("HumanoidRootPart") :: BasePart
			task.wait() -- let the character finish loading
			root.CFrame = cp.CFrame + Vector3.new(0, 4, 0)
		end
	end)
end

local function savePlayer(player: Player)
	local leaderstats = player:FindFirstChild("leaderstats")
	if not leaderstats then return end
	local data = {
		stage = (leaderstats:FindFirstChild("Stage") :: IntValue).Value,
		coins = (leaderstats:FindFirstChild("Coins") :: IntValue).Value,
	}
	local ok, err = pcall(function()
		stageStore:SetAsync(tostring(player.UserId), data)
	end)
	if not ok then warn("Could not save", player.Name, err) end
end

Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(savePlayer)
game:BindToClose(function()
	for _, player in Players:GetPlayers() do
		savePlayer(player)
	end
end)

------------------------------------------------------------------
-- Checkpoints: only advance one stage at a time (no skipping!)
------------------------------------------------------------------
for _, cp in checkpoints:GetChildren() do
	if not cp:IsA("BasePart") then continue end
	local number = tonumber(cp.Name)
	if not number then continue end

	cp.Touched:Connect(function(hit)
		local player = playerFromHit(hit)
		if not player then return end
		local stage = (player:FindFirstChild("leaderstats") :: Folder):FindFirstChild("Stage") :: IntValue
		if number == stage.Value + 1 then
			stage.Value = number
			cp.Color = Color3.fromRGB(80, 255, 120)
			task.delay(0.4, function() cp.Color = Color3.fromRGB(255, 255, 255) end)
		end
	end)
end

------------------------------------------------------------------
-- Kill bricks
------------------------------------------------------------------
for _, brick in killBricks:GetDescendants() do
	if brick:IsA("BasePart") then
		brick.Touched:Connect(function(hit)
			local _, humanoid = playerFromHit(hit)
			if humanoid then humanoid.Health = 0 end
		end)
	end
end

------------------------------------------------------------------
-- Coins (respawn after a delay)
------------------------------------------------------------------
for _, coin in coins:GetDescendants() do
	if not coin:IsA("BasePart") then continue end
	local active = true
	coin.Touched:Connect(function(hit)
		if not active then return end
		local player = playerFromHit(hit)
		if not player then return end
		active = false
		local stat = (player:FindFirstChild("leaderstats") :: Folder):FindFirstChild("Coins") :: IntValue
		stat.Value += COIN_VALUE
		coin.Transparency = 1
		coin.CanTouch = false
		task.delay(COIN_RESPAWN, function()
			coin.Transparency = 0
			coin.CanTouch = true
			active = true
		end)
	end)
end

-- Spin all coins slowly
RunService.Heartbeat:Connect(function(dt)
	for _, coin in coins:GetDescendants() do
		if coin:IsA("BasePart") then
			coin.CFrame *= CFrame.Angles(0, math.rad(90) * dt, 0)
		end
	end
end)

------------------------------------------------------------------
-- Moving platforms (back and forth with tweens)
------------------------------------------------------------------
if movers then
	for _, part in movers:GetDescendants() do
		if not part:IsA("BasePart") then continue end
		local offset = part:GetAttribute("Offset") or Vector3.new(0, 0, 12)
		local duration = part:GetAttribute("Duration") or 3
		part.Anchored = true
		local info = TweenInfo.new(duration, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true)
		TweenService:Create(part, info, { CFrame = part.CFrame + offset }):Play()
	end
end

------------------------------------------------------------------
-- Spinning obstacles
------------------------------------------------------------------
if spinners then
	RunService.Heartbeat:Connect(function(dt)
		for _, part in spinners:GetDescendants() do
			if part:IsA("BasePart") then
				local speed = part:GetAttribute("Speed") or 90
				part.CFrame *= CFrame.Angles(0, math.rad(speed) * dt, 0)
			end
		end
	end)
end
