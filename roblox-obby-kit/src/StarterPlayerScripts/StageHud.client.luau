--!strict
-- OBBY KIT (client): a simple stage banner that pops in each time you reach a new stage.
-- Put this LocalScript in StarterPlayer > StarterPlayerScripts.

local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")

local player = Players.LocalPlayer
local leaderstats = player:WaitForChild("leaderstats")
local stage = leaderstats:WaitForChild("Stage") :: IntValue

local gui = Instance.new("ScreenGui")
gui.Name = "StageHud"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local label = Instance.new("TextLabel")
label.AnchorPoint = Vector2.new(0.5, 0)
label.Position = UDim2.new(0.5, 0, 0, -80)
label.Size = UDim2.new(0, 320, 0, 60)
label.BackgroundColor3 = Color3.fromRGB(20, 16, 40)
label.BackgroundTransparency = 0.2
label.TextColor3 = Color3.fromRGB(94, 242, 255)
label.Font = Enum.Font.GothamBold
label.TextScaled = true
label.Parent = gui

local corner = Instance.new("UICorner")
corner.CornerRadius = UDim.new(0, 12)
corner.Parent = label

local stroke = Instance.new("UIStroke")
stroke.Color = Color3.fromRGB(255, 79, 216)
stroke.Thickness = 2
stroke.Parent = label

local showInfo = TweenInfo.new(0.5, Enum.EasingStyle.Back, Enum.EasingDirection.Out)
local hideInfo = TweenInfo.new(0.4, Enum.EasingStyle.Quad, Enum.EasingDirection.In)

local function announce(text: string)
	label.Text = text
	TweenService:Create(label, showInfo, { Position = UDim2.new(0.5, 0, 0, 30) }):Play()
	task.delay(2, function()
		TweenService:Create(label, hideInfo, { Position = UDim2.new(0.5, 0, 0, -80) }):Play()
	end)
end

announce("Stage " .. stage.Value)
stage.Changed:Connect(function(value)
	announce("✔ Stage " .. value .. "!")
end)
